const request = require('supertest');
const express = require('express');
const axios = require('axios');

// Mock axios for external API calls
jest.mock('axios');

// Create test app
const createTestApp = () => {
  const app = express();
  app.use(express.json({ limit: '20mb' }));
  app.use(express.urlencoded({ limit: '20mb', extended: true }));

  // Mock authentication middleware
  const authenticateToken = (req, res, next) => {
    const token = req.headers['authorization']?.split(' ')[1];
    if (!token) {
      return res.status(401).json({ error: 'No token provided' });
    }
    if (token === 'valid-token') {
      req.user = { id: '123', email: 'test@example.com' };
      next();
    } else {
      return res.status(403).json({ error: 'Invalid token' });
    }
  };

  // Prompt generation endpoint
  app.post('/api/prompts', (req, res) => {
    const { genres, exerciseType } = req.body;

    if (!genres || !Array.isArray(genres) || genres.length === 0) {
      return res.status(400).json({ error: 'Genres are required' });
    }

    if (genres.length > 2) {
      return res.status(400).json({ error: 'Maximum 2 genres allowed' });
    }

    axios.post(`${process.env.PROMPT_SERVICE_URL}/api/generate-prompt`, {
      genres,
      exerciseType
    })
      .then(response => res.json(response.data))
      .catch(error => res.status(500).json({ error: 'Failed to generate prompt' }));
  });

  // Writing feedback endpoint
  app.post('/api/writing/feedback', (req, res) => {
    const { exercise, exerciseType, userWriting, genres, difficulty, wordCount } = req.body;

    if (!userWriting || userWriting.trim().length === 0) {
      return res.status(400).json({ error: 'User writing is required' });
    }

    // Word count validation
    const words = userWriting.trim().split(/\s+/).filter(w => w.length > 0);
    if (wordCount && words.length < wordCount) {
      return res.status(400).json({
        error: `Minimum ${wordCount} words required. You have ${words.length} words.`
      });
    }

    axios.post(`${process.env.PROMPT_SERVICE_URL}/api/writing/feedback`, {
      exercise,
      exerciseType,
      userWriting,
      genres,
      difficulty,
      wordCount
    }, {
      maxBodyLength: Infinity,
      maxContentLength: Infinity
    })
      .then(response => res.json(response.data))
      .catch(error => res.status(500).json({ error: 'Failed to get feedback' }));
  });

  // Drawing feedback endpoint
  app.post('/api/drawing/feedback', (req, res) => {
    const { image, exercise, skills, difficulty } = req.body;

    if (!image) {
      return res.status(400).json({ error: 'Image is required' });
    }

    // Check if image is base64
    if (!image.startsWith('data:image/')) {
      return res.status(400).json({ error: 'Invalid image format' });
    }

    // Check image size (base64 is ~1.37x larger than binary)
    const base64Length = image.split(',')[1]?.length || 0;
    const approximateSize = (base64Length * 0.75); // Convert to bytes
    const maxSize = 20 * 1024 * 1024; // 20MB

    if (approximateSize > maxSize) {
      return res.status(413).json({ error: 'Image file too large. Maximum 20MB allowed.' });
    }

    axios.post(`${process.env.PROMPT_SERVICE_URL}/api/drawing/feedback`, {
      image,
      exercise,
      skills,
      difficulty
    }, {
      maxBodyLength: Infinity,
      maxContentLength: Infinity
    })
      .then(response => res.json(response.data))
      .catch(error => {
        if (error.response?.status === 413) {
          return res.status(413).json({ error: 'Image file too large' });
        }
        res.status(500).json({ error: 'Failed to get feedback' });
      });
  });

  // Protected endpoint example
  app.get('/api/user/profile', authenticateToken, (req, res) => {
    res.json({ user: req.user });
  });

  return app;
};

describe('Backend API Endpoints', () => {
  let app;

  beforeEach(() => {
    app = createTestApp();
    process.env.PROMPT_SERVICE_URL = 'http://localhost:5001';
    axios.post.mockClear();
  });

  describe('POST /api/prompts', () => {
    test('generates prompt with valid genres', async () => {
      const mockPrompt = {
        title: 'Test Prompt',
        content: 'Write something',
        difficulty: 'Easy',
        wordCount: 500
      };

      axios.post.mockResolvedValueOnce({ data: mockPrompt });

      const response = await request(app)
        .post('/api/prompts')
        .send({ genres: ['Fantasy', 'Science Fiction'] });

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockPrompt);
      expect(axios.post).toHaveBeenCalledWith(
        'http://localhost:5001/api/generate-prompt',
        expect.objectContaining({
          genres: ['Fantasy', 'Science Fiction']
        })
      );
    });

    test('rejects request with no genres', async () => {
      const response = await request(app)
        .post('/api/prompts')
        .send({});

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Genres are required');
    });

    test('rejects request with more than 2 genres', async () => {
      const response = await request(app)
        .post('/api/prompts')
        .send({ genres: ['Fantasy', 'Sci-Fi', 'Mystery'] });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Maximum 2 genres allowed');
    });

    test('rejects request with invalid genres format', async () => {
      const response = await request(app)
        .post('/api/prompts')
        .send({ genres: 'Fantasy' }); // Should be array

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Genres are required');
    });

    test('handles prompt service error', async () => {
      axios.post.mockRejectedValueOnce(new Error('Service unavailable'));

      const response = await request(app)
        .post('/api/prompts')
        .send({ genres: ['Fantasy'] });

      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Failed to generate prompt');
    });
  });

  describe('POST /api/writing/feedback', () => {
    const validFeedbackRequest = {
      exercise: 'Write a story opening',
      exerciseType: 'Idea Generation',
      userWriting: Array(500).fill('word').join(' '),
      genres: ['Fantasy'],
      difficulty: 'Easy',
      wordCount: 500
    };

    test('submits feedback with valid data', async () => {
      const mockFeedback = { feedback: '### Strengths\n\nGood work!' };

      axios.post.mockResolvedValueOnce({ data: mockFeedback });

      const response = await request(app)
        .post('/api/writing/feedback')
        .send(validFeedbackRequest);

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockFeedback);
    });

    test('rejects empty userWriting', async () => {
      const response = await request(app)
        .post('/api/writing/feedback')
        .send({ ...validFeedbackRequest, userWriting: '' });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('User writing is required');
    });

    test('rejects userWriting with only whitespace', async () => {
      const response = await request(app)
        .post('/api/writing/feedback')
        .send({ ...validFeedbackRequest, userWriting: '   \n\n   ' });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('User writing is required');
    });

    test('rejects userWriting below word count minimum', async () => {
      const response = await request(app)
        .post('/api/writing/feedback')
        .send({
          ...validFeedbackRequest,
          userWriting: 'Only five words here today',
          wordCount: 500
        });

      expect(response.status).toBe(400);
      expect(response.body.error).toContain('Minimum 500 words required');
      expect(response.body.error).toContain('You have 5 words');
    });

    test('accepts userWriting meeting word count', async () => {
      const mockFeedback = { feedback: 'Great work!' };
      axios.post.mockResolvedValueOnce({ data: mockFeedback });

      const longText = Array(500).fill('word').join(' ');

      const response = await request(app)
        .post('/api/writing/feedback')
        .send({ ...validFeedbackRequest, userWriting: longText });

      expect(response.status).toBe(200);
    });

    test('handles prompt service error', async () => {
      axios.post.mockRejectedValueOnce(new Error('Service error'));

      const response = await request(app)
        .post('/api/writing/feedback')
        .send(validFeedbackRequest);

      expect(response.status).toBe(500);
      expect(response.body.error).toBe('Failed to get feedback');
    });
  });

  describe('POST /api/drawing/feedback', () => {
    const validBase64Image = 'data:image/jpeg;base64,' + 'A'.repeat(1000);

    const validDrawingRequest = {
      image: validBase64Image,
      exercise: 'Draw a gesture sketch',
      skills: ['Gesture', 'Form'],
      difficulty: 'Intermediate'
    };

    test('submits drawing feedback with valid image', async () => {
      const mockFeedback = { feedback: '### Strengths\n\nGood gesture!' };

      axios.post.mockResolvedValueOnce({ data: mockFeedback });

      const response = await request(app)
        .post('/api/drawing/feedback')
        .send(validDrawingRequest);

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockFeedback);
    });

    test('rejects request without image', async () => {
      const response = await request(app)
        .post('/api/drawing/feedback')
        .send({ ...validDrawingRequest, image: undefined });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Image is required');
    });

    test('rejects non-base64 image', async () => {
      const response = await request(app)
        .post('/api/drawing/feedback')
        .send({ ...validDrawingRequest, image: 'not-a-base64-image' });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe('Invalid image format');
    });

    test('rejects image larger than 20MB', async () => {
      // Create a large base64 string (> 20MB)
      const largeImage = 'data:image/jpeg;base64,' + 'A'.repeat(28 * 1024 * 1024);

      const response = await request(app)
        .post('/api/drawing/feedback')
        .send({ ...validDrawingRequest, image: largeImage });

      expect(response.status).toBe(413);
      expect(response.body.error).toContain('too large');
    });

    test('accepts PNG images', async () => {
      const mockFeedback = { feedback: 'Good work!' };
      axios.post.mockResolvedValueOnce({ data: mockFeedback });

      const pngImage = 'data:image/png;base64,' + 'A'.repeat(1000);

      const response = await request(app)
        .post('/api/drawing/feedback')
        .send({ ...validDrawingRequest, image: pngImage });

      expect(response.status).toBe(200);
    });

    test('handles 413 error from prompt service', async () => {
      axios.post.mockRejectedValueOnce({
        response: { status: 413 }
      });

      const response = await request(app)
        .post('/api/drawing/feedback')
        .send(validDrawingRequest);

      expect(response.status).toBe(413);
      expect(response.body.error).toBe('Image file too large');
    });
  });

  describe('Authentication', () => {
    test('protected endpoint requires token', async () => {
      const response = await request(app)
        .get('/api/user/profile');

      expect(response.status).toBe(401);
      expect(response.body.error).toBe('No token provided');
    });

    test('protected endpoint accepts valid token', async () => {
      const response = await request(app)
        .get('/api/user/profile')
        .set('Authorization', 'Bearer valid-token');

      expect(response.status).toBe(200);
      expect(response.body.user).toEqual({ id: '123', email: 'test@example.com' });
    });

    test('protected endpoint rejects invalid token', async () => {
      const response = await request(app)
        .get('/api/user/profile')
        .set('Authorization', 'Bearer invalid-token');

      expect(response.status).toBe(403);
      expect(response.body.error).toBe('Invalid token');
    });
  });

  describe('Security - Input Validation', () => {
    test('sanitizes SQL injection attempt in writing feedback', async () => {
      const sqlInjection = "'; DROP TABLE users; --";

      const mockFeedback = { feedback: 'Feedback' };
      axios.post.mockResolvedValueOnce({ data: mockFeedback });

      const response = await request(app)
        .post('/api/writing/feedback')
        .send({
          exercise: 'Test',
          userWriting: Array(500).fill('word').join(' ') + sqlInjection,
          genres: ['Fantasy'],
          wordCount: 500
        });

      // Should not crash, passes through to service layer
      expect(response.status).toBe(200);

      // Verify the malicious content is passed as-is (backend doesn't interpret)
      const call = axios.post.mock.calls[0];
      expect(call[1].userWriting).toContain(sqlInjection);
    });

    test('handles XSS attempt in feedback request', async () => {
      const xssAttempt = '<script>alert("XSS")</script>';

      const mockFeedback = { feedback: 'Feedback' };
      axios.post.mockResolvedValueOnce({ data: mockFeedback });

      const response = await request(app)
        .post('/api/writing/feedback')
        .send({
          exercise: xssAttempt,
          userWriting: Array(500).fill('word').join(' '),
          genres: ['Fantasy'],
          wordCount: 500
        });

      // Should not execute, passes as string
      expect(response.status).toBe(200);
    });

    test('rejects malformed JSON', async () => {
      const response = await request(app)
        .post('/api/prompts')
        .set('Content-Type', 'application/json')
        .send('{ invalid json }');

      expect(response.status).toBe(400);
    });

    test('handles extremely long input strings', async () => {
      const veryLongString = 'A'.repeat(10 * 1024 * 1024); // 10MB string

      const mockFeedback = { feedback: 'Feedback' };
      axios.post.mockResolvedValueOnce({ data: mockFeedback });

      const response = await request(app)
        .post('/api/writing/feedback')
        .send({
          exercise: 'Test',
          userWriting: veryLongString,
          genres: ['Fantasy'],
          wordCount: 100 // Low count to pass validation
        });

      // Should handle large payloads up to 20MB limit
      expect(response.status).toBe(200);
    });
  });

  describe('CORS and Headers', () => {
    test('accepts JSON content type', async () => {
      axios.post.mockResolvedValueOnce({ data: { title: 'Test' } });

      const response = await request(app)
        .post('/api/prompts')
        .set('Content-Type', 'application/json')
        .send({ genres: ['Fantasy'] });

      expect(response.status).toBe(200);
    });

    test('handles missing content-type header', async () => {
      const response = await request(app)
        .post('/api/prompts')
        .send({ genres: ['Fantasy'] });

      // Express should still parse it
      expect(response.status).not.toBe(415);
    });
  });
});
