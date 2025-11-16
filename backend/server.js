const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { Pool } = require('pg');
const Redis = require('ioredis');
const jwt = require('jsonwebtoken');
const { OAuth2Client } = require('google-auth-library');
const { trace, metrics } = require('@opentelemetry/api');
const { PrometheusExporter } = require('@opentelemetry/exporter-prometheus');
const { MeterProvider } = require('@opentelemetry/sdk-metrics');
const { NodeTracerProvider } = require('@opentelemetry/sdk-trace-node');
const { registerInstrumentations } = require('@opentelemetry/instrumentation');
const { HttpInstrumentation } = require('@opentelemetry/instrumentation-http');
const { ExpressInstrumentation } = require('@opentelemetry/instrumentation-express');
const axios = require('axios');
const pagerduty = require('node-pagerduty');

// Initialize OpenTelemetry
const tracerProvider = new NodeTracerProvider();
tracerProvider.register();

registerInstrumentations({
  instrumentations: [
    new HttpInstrumentation(),
    new ExpressInstrumentation(),
  ],
});

const tracer = trace.getTracer('backend-api');

// Initialize Prometheus metrics
const prometheusExporter = new PrometheusExporter(
  {
    port: 9464,
    endpoint: '/metrics',
  },
  () => {
    console.log('Prometheus metrics server started on port 9464');
  }
);

const meterProvider = new MeterProvider();
meterProvider.addMetricReader(prometheusExporter);
metrics.setGlobalMeterProvider(meterProvider);

const meter = metrics.getMeter('backend-api');

// Create custom metrics
const requestCounter = meter.createCounter('http_requests_total', {
  description: 'Total number of HTTP requests',
});

const requestDuration = meter.createHistogram('http_request_duration_seconds', {
  description: 'HTTP request duration in seconds',
});

const promptGenerationCounter = meter.createCounter('prompts_generated_total', {
  description: 'Total number of prompts generated',
});

// Initialize app
const app = express();
const port = process.env.PORT || 4000;

// Database connection
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

// Redis connection
const redis = new Redis(process.env.REDIS_URL);

// Google OAuth client
const googleClient = new OAuth2Client(process.env.GOOGLE_CLIENT_ID);

// PagerDuty client
const pd = new pagerduty(process.env.PAGERDUTY_API_KEY);

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Request logging and metrics middleware
app.use((req, res, next) => {
  const startTime = Date.now();
  
  requestCounter.add(1, {
    method: req.method,
    route: req.path,
  });

  res.on('finish', () => {
    const duration = (Date.now() - startTime) / 1000;
    requestDuration.record(duration, {
      method: req.method,
      route: req.path,
      status_code: res.statusCode,
    });
  });

  next();
});

// Health check endpoint
app.get('/health', async (req, res) => {
  const span = tracer.startSpan('health-check');
  
  try {
    await pool.query('SELECT 1');
    await redis.ping();
    
    span.setStatus({ code: 1 });
    res.json({ status: 'healthy', timestamp: new Date().toISOString() });
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    
    // Send PagerDuty alert for critical health check failure
    await sendPagerDutyAlert('Health check failed', error.message, 'critical');
    
    res.status(503).json({ status: 'unhealthy', error: error.message });
  } finally {
    span.end();
  }
});

// Google OAuth authentication
app.post('/api/auth/google', async (req, res) => {
  const span = tracer.startSpan('google-auth');
  
  try {
    const { credential } = req.body;
    
    const ticket = await googleClient.verifyIdToken({
      idToken: credential,
      audience: process.env.GOOGLE_CLIENT_ID,
    });
    
    const payload = ticket.getPayload();
    
    // Store user in database
    const user = await pool.query(
      `INSERT INTO users (google_id, email, name, picture) 
       VALUES ($1, $2, $3, $4) 
       ON CONFLICT (google_id) 
       DO UPDATE SET 
         email = EXCLUDED.email,
         name = EXCLUDED.name,
         picture = EXCLUDED.picture,
         last_login = NOW()
       RETURNING *`,
      [payload.sub, payload.email, payload.name, payload.picture]
    );
    
    // Generate JWT
    const token = jwt.sign(
      { 
        id: user.rows[0].id,
        email: user.rows[0].email 
      },
      process.env.JWT_SECRET,
      { expiresIn: '7d' }
    );
    
    // Cache user session in Redis
    await redis.setex(`session:${user.rows[0].id}`, 604800, JSON.stringify(user.rows[0]));
    
    span.setStatus({ code: 1 });
    res.json({
      token,
      user: user.rows[0]
    });
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    res.status(401).json({ error: 'Authentication failed' });
  } finally {
    span.end();
  }
});

// Generate writing prompt
app.post('/api/prompts/generate', authenticateToken, async (req, res) => {
  const span = tracer.startSpan('generate-prompt');
  
  try {
    const { genres } = req.body;
    const userId = req.user.id;
    
    span.setAttributes({
      'user.id': userId,
      'genres.count': genres.length,
      'genres.selected': genres.join(',')
    });
    
    // Check rate limiting
    const rateLimitKey = `rate_limit:${userId}`;
    const requestCount = await redis.incr(rateLimitKey);
    
    if (requestCount === 1) {
      await redis.expire(rateLimitKey, 3600); // 1 hour window
    }
    
    if (requestCount > 100) { // 100 requests per hour limit
      span.setStatus({ code: 2, message: 'Rate limit exceeded' });
      return res.status(429).json({ error: 'Rate limit exceeded' });
    }
    
    
    // Call Python prompt generation service
    const promptServiceResponse = await axios.post('http://prompt-service:5001/generate', {
      genres,
      userId
    }, {
      timeout: 10000,
      headers: {
        'X-Request-ID': span.spanContext().traceId
      }
    });
    
    const prompt = promptServiceResponse.data;
    
    
    // Store in database
    await logPromptGeneration(userId, genres, prompt);
    
    // Send webhook notification if configured
    await sendWebhookNotification(userId, prompt);
    
    promptGenerationCounter.add(1, { source: 'generated' });
    span.setStatus({ code: 1 });
    res.json(prompt);
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    
    // Send PagerDuty alert for service failures
    if (error.code === 'ECONNREFUSED') {
      await sendPagerDutyAlert('Prompt service unavailable', error.message, 'high');
    }
    
    res.status(500).json({ error: 'Failed to generate prompt' });
  } finally {
    span.end();
  }
});

// Generate sound design prompt
app.post('/api/sound-design/generate', authenticateToken, async (req, res) => {
  const span = tracer.startSpan('generate-sound-design-prompt');

  try {
    const { synthesizer, exerciseType, genre } = req.body;
    const userId = req.user.id;

    span.setAttributes({
      'user.id': userId,
      'synthesizer': synthesizer,
      'exercise.type': exerciseType,
      'genre': genre || 'all'
    });

    // Validate inputs
    const validSynths = ['Serum 2', 'Phase Plant', 'Vital'];
    const validTypes = ['technical', 'creative'];
    const validGenres = ['all', 'dubstep', 'glitch-hop', 'dnb', 'experimental-bass', 'house', 'psytrance', 'hard-techno'];

    if (!synthesizer || !validSynths.includes(synthesizer)) {
      span.setStatus({ code: 2, message: 'Invalid synthesizer' });
      return res.status(400).json({ error: 'Invalid synthesizer selection' });
    }

    if (!exerciseType || !validTypes.includes(exerciseType)) {
      span.setStatus({ code: 2, message: 'Invalid exercise type' });
      return res.status(400).json({ error: 'Invalid exercise type' });
    }

    // Validate genre (optional, defaults to 'all')
    const selectedGenre = genre || 'all';
    if (!validGenres.includes(selectedGenre)) {
      span.setStatus({ code: 2, message: 'Invalid genre' });
      return res.status(400).json({ error: 'Invalid genre selection' });
    }

    // Call Python prompt generation service
    const promptServiceResponse = await axios.post('http://prompt-service:5001/generate-sound-design', {
      synthesizer,
      exerciseType,
      genre: selectedGenre,
      userId
    }, {
      timeout: 10000,
      headers: {
        'X-Request-ID': span.spanContext().traceId
      }
    });

    const prompt = promptServiceResponse.data;

    span.setStatus({ code: 1 });
    res.json(prompt);
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });

    console.error('Sound design prompt generation error:', error);
    res.status(500).json({ error: 'Failed to generate sound design prompt' });
  } finally {
    span.end();
  }
});

// Generate chord progression
app.post('/api/chord-progression/generate', async (req, res) => {
  const span = tracer.startSpan('chord-progression-generate');

  try {
    const { emotions, userId } = req.body;

    span.setAttributes({
      'user.id': userId || 'anonymous',
      'emotions': JSON.stringify(emotions)
    });

    // Call prompt service
    const promptServiceResponse = await axios.post(
      'http://prompt-service:5001/generate-chord-progression',
      {
        emotions,
        userId: userId || 'anonymous'
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': span.spanContext().traceId
        }
      }
    );

    const progression = promptServiceResponse.data;

    span.setStatus({ code: 1 });
    res.json(progression);
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });

    console.error('Chord progression generation error:', error);
    res.status(500).json({ error: 'Failed to generate chord progression' });
  } finally {
    span.end();
  }
});

app.post('/api/drawing/generate', async (req, res) => {
  const span = tracer.startSpan('drawing-exercise-generate');

  try {
    const { skills, userId } = req.body;

    span.setAttributes({
      'user.id': userId || 'anonymous',
      'skills': JSON.stringify(skills)
    });

    // Call prompt service
    const promptServiceResponse = await axios.post(
      'http://prompt-service:5001/generate-drawing-exercise',
      {
        skills,
        userId: userId || 'anonymous'
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': span.spanContext().traceId
        }
      }
    );

    const exercise = promptServiceResponse.data;

    span.setStatus({ code: 1 });
    res.json(exercise);
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });

    console.error('Drawing exercise generation error:', error);
    res.status(500).json({ error: 'Failed to generate drawing exercise' });
  } finally {
    span.end();
  }
});

// Writing feedback endpoint
app.post('/api/writing/feedback', async (req, res) => {
  const span = tracer.startSpan('writing-feedback-generate');

  try {
    const { exercise, exerciseType, userWriting, genres, difficulty, wordCount } = req.body;

    span.setAttributes({
      'exercise.type': exerciseType,
      'genres': JSON.stringify(genres),
      'difficulty': difficulty,
      'wordCount.target': wordCount,
      'wordCount.actual': userWriting.split(/\s+/).filter(w => w.length > 0).length
    });

    // Call prompt service
    const promptServiceResponse = await axios.post(
      'http://prompt-service:5001/generate-writing-feedback',
      {
        exercise,
        exerciseType,
        userWriting,
        genres,
        difficulty,
        wordCount
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'X-Request-ID': span.spanContext().traceId
        }
      }
    );

    const feedback = promptServiceResponse.data;

    span.setStatus({ code: 1 });
    res.json(feedback);
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });

    console.error('Writing feedback generation error:', error);
    res.status(500).json({ error: 'Failed to generate writing feedback' });
  } finally {
    span.end();
  }
});

// Get user's prompt history
app.get('/api/prompts/history', authenticateToken, async (req, res) => {
  const span = tracer.startSpan('get-prompt-history');
  
  try {
    const userId = req.user.id;
    const { limit = 20, offset = 0 } = req.query;
    
    const result = await pool.query(
      `SELECT p.*, array_agg(pg.genre) as genres
       FROM prompts p
       JOIN prompt_genres pg ON p.id = pg.prompt_id
       WHERE p.user_id = $1
       GROUP BY p.id
       ORDER BY p.created_at DESC
       LIMIT $2 OFFSET $3`,
      [userId, limit, offset]
    );
    
    span.setStatus({ code: 1 });
    res.json(result.rows);
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    res.status(500).json({ error: 'Failed to fetch history' });
  } finally {
    span.end();
  }
});

// Webhook endpoint for external integrations
app.post('/api/webhooks/prompt-generated', async (req, res) => {
  const span = tracer.startSpan('webhook-prompt-generated');
  
  try {
    const { secret, data } = req.body;
    
    // Verify webhook secret
    if (secret !== process.env.WEBHOOK_SECRET) {
      span.setStatus({ code: 2, message: 'Invalid webhook secret' });
      return res.status(401).json({ error: 'Unauthorized' });
    }
    
    // Process webhook data (e.g., trigger notifications, analytics, etc.)
    console.log('Webhook received:', data);
    
    span.setStatus({ code: 1 });
    res.json({ status: 'received' });
  } catch (error) {
    span.recordException(error);
    span.setStatus({ code: 2, message: error.message });
    res.status(500).json({ error: 'Webhook processing failed' });
  } finally {
    span.end();
  }
});

// Helper functions
function authenticateToken(req, res, next) {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  
  if (!token) {
    return res.sendStatus(401);
  }
  
  jwt.verify(token, process.env.JWT_SECRET, (err, user) => {
    if (err) {
      return res.sendStatus(403);
    }
    req.user = user;
    next();
  });
}

async function logPromptGeneration(userId, genres, prompt) {
  const client = await pool.connect();
  
  try {
    await client.query('BEGIN');
    
    const promptResult = await client.query(
      `INSERT INTO prompts (user_id, title, content, difficulty, word_count)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING id`,
      [userId, prompt.title, prompt.content, prompt.difficulty, prompt.wordCount]
    );
    
    const promptId = promptResult.rows[0].id;
    
    // Insert genres
    for (const genre of genres) {
      await client.query(
        `INSERT INTO prompt_genres (prompt_id, genre) VALUES ($1, $2)`,
        [promptId, genre]
      );
    }
    
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

async function sendWebhookNotification(userId, prompt) {
  try {
    const user = await pool.query('SELECT webhook_url FROM users WHERE id = $1', [userId]);
    
    if (user.rows[0]?.webhook_url) {
      await axios.post(user.rows[0].webhook_url, {
        event: 'prompt_generated',
        data: prompt,
        timestamp: new Date().toISOString()
      }, {
        timeout: 5000
      });
    }
  } catch (error) {
    console.error('Webhook notification failed:', error);
    // Don't throw - webhook failures shouldn't break the main flow
  }
}

async function sendPagerDutyAlert(title, details, urgency = 'low') {
  if (!process.env.PAGERDUTY_API_KEY) {
    return;
  }
  
  try {
    await pd.events.sendEvent({
      routing_key: process.env.PAGERDUTY_ROUTING_KEY,
      event_action: 'trigger',
      payload: {
        summary: title,
        source: 'writing-prompt-generator',
        severity: urgency === 'critical' ? 'critical' : urgency === 'high' ? 'error' : 'warning',
        custom_details: details
      }
    });
  } catch (error) {
    console.error('PagerDuty alert failed:', error);
  }
}

// Start server
app.listen(port, () => {
  console.log(`Backend API running on port ${port}`);
  console.log(`Metrics available at http://localhost:9464/metrics`);
});

// Graceful shutdown
process.on('SIGTERM', async () => {
  console.log('SIGTERM received, shutting down gracefully');
  await pool.end();
  await redis.quit();
  process.exit(0);
});
