from flask import Flask, request, jsonify
from flask_cors import CORS
import redis
import json
import random
import hashlib
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import logging
import os
from datetime import datetime
import openai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize OpenTelemetry
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4318') + '/v1/traces',
)

span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Instrument Flask and requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Redis connection
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))

# OpenAI configuration (optional - will fallback to template-based generation)
openai_api_key = os.getenv('OPENAI_API_KEY')
if openai_api_key:
    openai.api_key = openai_api_key
    USE_AI = True
else:
    USE_AI = False
    logger.info("OpenAI API key not found, using template-based generation")

# Prompt templates for fallback generation
PROMPT_TEMPLATES = {
    'Fantasy': [
        {
            'title': 'The Last Dragon\'s Secret',
            'template': 'In a world where dragons were thought extinct, {character} discovers {discovery} hidden in {location}. As {conflict} threatens the realm, they must {challenge} before {deadline}.',
            'elements': {
                'character': ['a young apprentice mage', 'an exiled knight', 'a street thief with unusual talents'],
                'discovery': ['a dragon egg', 'an ancient prophecy', 'a map to the dragon sanctuary'],
                'location': ['the royal library\'s forbidden section', 'an abandoned tower', 'beneath the city sewers'],
                'conflict': ['a dark sorcerer\'s army', 'a plague of shadows', 'civil war'],
                'challenge': ['master forbidden magic', 'unite warring kingdoms', 'awaken the sleeping dragon'],
                'deadline': ['the blood moon rises', 'winter\'s first snow', 'the king\'s coronation']
            }
        }
    ],
    'Science Fiction': [
        {
            'title': 'Colony Ship Paradox',
            'template': 'The generation ship {ship_name} has been traveling for {duration}, but {character} discovers {revelation}. With {resource} running low and {threat} approaching, they must decide whether to {choice}.',
            'elements': {
                'ship_name': ['Horizon\'s Hope', 'New Eden', 'Stellar Ark'],
                'duration': ['300 years', '50 generations', 'longer than recorded history'],
                'character': ['the ship\'s AI maintenance tech', 'a historian studying old Earth', 'the youngest council member'],
                'revelation': ['they\'ve been traveling in circles', 'Earth still exists', 'the ship is actually a prison'],
                'resource': ['oxygen', 'genetic diversity', 'hope'],
                'threat': ['an alien armada', 'system-wide cascade failure', 'a mutiny'],
                'choice': ['wake the frozen founders', 'change course to an unknown planet', 'reveal the truth to everyone']
            }
        }
    ],
    'Mystery': [
        {
            'title': 'The Vanishing Gallery',
            'template': '{character} arrives at {location} to investigate {mystery}. The only clue is {clue}, but {complication} makes everyone a suspect. The truth involves {twist}.',
            'elements': {
                'character': ['a retired detective', 'an insurance investigator', 'an art student'],
                'location': ['a private island museum', 'a underground auction house', 'a restored Victorian mansion'],
                'mystery': ['the disappearance of priceless paintings', 'a murder during a locked-room auction', 'forged masterpieces appearing worldwide'],
                'clue': ['a half-burned photograph', 'a coded message in the victim\'s notebook', 'paint that shouldn\'t exist yet'],
                'complication': ['everyone has an alibi', 'the security footage has been edited', 'the victim is still alive'],
                'twist': ['time travel', 'identical twins nobody knew about', 'the detective is the criminal']
            }
        }
    ],
    'Horror': [
        {
            'title': 'The Inheritance',
            'template': '{character} inherits {inheritance} from {relative}, but discovers {horror} lurking within. As {event} approaches, they realize {revelation} and must {action} to survive.',
            'elements': {
                'character': ['a struggling artist', 'a medical student', 'a single parent'],
                'inheritance': ['a Victorian mansion', 'an antique shop', 'a storage unit full of artifacts'],
                'relative': ['an uncle they never knew existed', 'their recently deceased grandmother', 'a distant cousin'],
                'horror': ['the previous owners never left', 'a portal to somewhere else', 'a curse that transfers to the new owner'],
                'event': ['the anniversary of a tragedy', 'a lunar eclipse', 'their first night alone'],
                'revelation': ['they were chosen for a reason', 'their family has kept this secret for generations', 'escaping makes it worse'],
                'action': ['perform an ancient ritual', 'burn everything', 'make a terrible sacrifice']
            }
        }
    ],
    'Romance': [
        {
            'title': 'Second Chances',
            'template': '{character1} and {character2} meet again after {time_period} at {location}. Despite {obstacle}, they discover {connection}, but {conflict} threatens to {consequence}.',
            'elements': {
                'character1': ['a successful CEO', 'a small-town teacher', 'a traveling musician'],
                'character2': ['their college sweetheart', 'their former rival', 'their best friend\'s sibling'],
                'time_period': ['ten years', 'a lifetime', 'one unforgettable summer'],
                'location': ['a destination wedding', 'their hometown reunion', 'an unexpected flight delay'],
                'obstacle': ['they\'re both engaged to others', 'a bitter misunderstanding', 'completely different lives now'],
                'connection': ['they still finish each other\'s sentences', 'a shared dream they never forgot', 'letters never sent'],
                'conflict': ['a job opportunity abroad', 'family disapproval', 'a secret from the past'],
                'consequence': ['separate them forever', 'change everything', 'break other hearts']
            }
        }
    ]
}

def get_random_word_count_and_difficulty():
    """Randomly select word count and corresponding difficulty"""
    options = [
        (250, 'Very Easy'),
        (500, 'Easy'),
        (750, 'Medium'),
        (1000, 'Hard')
    ]
    word_count, difficulty = random.choice(options)
    return word_count, difficulty

def generate_prompt_from_template(genres):
    """Generate a writing prompt using templates when AI is not available"""
    selected_templates = []
    
    for genre in genres:
        if genre in PROMPT_TEMPLATES:
            selected_templates.extend(PROMPT_TEMPLATES[genre])
    
    if not selected_templates:
        # Default template if no matching genres
        selected_templates = [
            {
                'title': 'The Unexpected Journey',
                'template': 'Your protagonist discovers {discovery} that changes everything they believed about {belief}. They must {action} before {deadline}.',
                'elements': {
                    'discovery': ['a hidden letter', 'a secret door', 'an old photograph'],
                    'belief': ['their family history', 'their own identity', 'the nature of reality'],
                    'action': ['uncover the truth', 'make an impossible choice', 'confront their fears'],
                    'deadline': ['it\'s too late', 'someone else finds out', 'the opportunity disappears']
                }
            }
        ]
    
    # Select random template
    template_data = random.choice(selected_templates)
    template = template_data['template']
    elements = template_data['elements']
    
    # Fill in the template
    prompt_text = template
    for key, options in elements.items():
        prompt_text = prompt_text.replace(f'{{{key}}}', random.choice(options))
    
    # Get random word count and difficulty
    word_count, difficulty = get_random_word_count_and_difficulty()    
    return {
        'title': template_data['title'],
        'content': prompt_text,
        'genres': genres,
        'difficulty': difficulty,
        'wordCount': word_count,
        'tips': generate_writing_tips(genres),
        'timestamp': datetime.utcnow().isoformat()
    }

def generate_prompt_with_ai(genres):
    """Generate a writing prompt using OpenAI API"""
    genre_string = ", ".join(genres)
    
    system_prompt = """You are a creative writing prompt generator. Create engaging, detailed writing prompts that inspire writers. Each prompt should:
    1. Set up an intriguing scenario
    2. Introduce a compelling conflict or mystery
    3. Hint at stakes or consequences
    4. Leave room for creative interpretation
    5. Be suitable for the specified genres"""
    
    user_prompt = f"""Create a writing prompt that combines these genres: {genre_string}
    
    The prompt should be 2-3 sentences long and spark creativity.
    Also suggest a compelling title for the story."""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.9,
            max_tokens=200
        )
        
        content = response.choices[0].message.content
        
        # Parse response (assuming format: "Title: XXX\n\nPrompt: YYY")
        lines = content.split('\n')
        title = lines[0].replace('Title:', '').strip() if lines else 'Untitled Prompt'
        prompt_text = '\n'.join(lines[2:]).replace('Prompt:', '').strip() if len(lines) > 2 else content
        
        # Get random word count and difficulty
        word_count, difficulty = get_random_word_count_and_difficulty()        
        return {
            'title': title,
            'content': prompt_text,
            'genres': genres,
            'difficulty': difficulty,
            'wordCount': word_count,
            'tips': generate_writing_tips(genres),
            'timestamp': datetime.utcnow().isoformat(),
            'ai_generated': True
        }
    except Exception as e:
        logger.error(f"AI generation failed: {str(e)}")
        # Fallback to template generation
        return generate_prompt_from_template(genres)

def generate_writing_tips(genres):
    """Generate writing tips based on selected genres"""
    tips = []
    
    genre_tips = {
        'Fantasy': 'Build a consistent magic system with clear rules and limitations.',
        'Science Fiction': 'Ground your technology in real scientific concepts, even if extrapolated.',
        'Mystery': 'Plant clues fairly throughout the story - readers should be able to solve it.',
        'Horror': 'Build tension through atmosphere and pacing, not just jump scares.',
        'Romance': 'Develop both characters fully - they should be interesting apart and together.',
        'Thriller': 'Keep the pacing tight and end chapters with hooks.',
        'Historical Fiction': 'Research the period thoroughly but don\'t let facts overwhelm the story.',
        'Literary Fiction': 'Focus on character development and thematic depth.',
        'Young Adult': 'Address serious themes while maintaining an authentic teen voice.',
        'Crime': 'Make your detective\'s process logical and methodical.',
        'Adventure': 'Balance action sequences with character moments.',
        'Dystopian': 'Create a believable path from our world to yours.',
        'Magical Realism': 'Treat magical elements as mundane parts of the world.',
        'Western': 'Focus on themes of justice, freedom, and survival.',
        'Biography': 'Find the narrative arc in real events.',
        'Self-Help': 'Provide actionable advice with real-world examples.',
        'Philosophy': 'Make abstract concepts concrete through examples.',
        'Poetry': 'Show rather than tell - use vivid imagery.'
    }
    
    for genre in genres:
        if genre in genre_tips:
            tips.append(genre_tips[genre])
    
    # Add general tips
    tips.append('Start with a strong opening line that immediately engages the reader.')
    tips.append('Show character growth through actions and decisions, not just description.')
    
    return tips[:3]  # Return top 3 tips

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    with tracer.start_as_current_span("health-check"):
        try:
            redis_client.ping()
            return jsonify({'status': 'healthy', 'service': 'prompt-generator'}), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

@app.route('/generate', methods=['POST'])
def generate():
    """Generate a writing prompt based on selected genres"""
    with tracer.start_as_current_span("generate-prompt") as span:
        try:
            data = request.json
            genres = data.get('genres', [])
            user_id = data.get('userId', 'anonymous')
            
            span.set_attribute("user.id", user_id)
            span.set_attribute("genres.count", len(genres))
            span.set_attribute("genres.list", ','.join(genres))
            
            if not genres:
                return jsonify({'error': 'At least one genre must be selected'}), 400
            
            # Generate cache key
            
            # Generate new prompt
            span.add_event("generating-new-prompt")
            
            if USE_AI:
                prompt = generate_prompt_with_ai(genres)
            else:
                prompt = generate_prompt_from_template(genres)
            
            
            # Track metrics
            span.set_attribute("prompt.title", prompt['title'])
            span.set_attribute("prompt.difficulty", prompt['difficulty'])
            span.set_attribute("prompt.word_count", prompt['wordCount'])
            
            return jsonify(prompt), 200
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Prompt generation failed: {str(e)}")
            return jsonify({'error': 'Failed to generate prompt'}), 500

@app.route('/feedback', methods=['POST'])
def feedback():
    """Collect feedback on generated prompts"""
    with tracer.start_as_current_span("prompt-feedback") as span:
        try:
            data = request.json
            prompt_id = data.get('promptId')
            rating = data.get('rating')
            user_id = data.get('userId', 'anonymous')
            
            span.set_attribute("user.id", user_id)
            span.set_attribute("prompt.id", prompt_id)
            span.set_attribute("feedback.rating", rating)
            
            # Store feedback in Redis
            feedback_key = f"feedback:{prompt_id}:{user_id}"
            redis_client.setex(
                feedback_key,
                86400 * 30,  # 30 days TTL
                json.dumps({
                    'rating': rating,
                    'timestamp': datetime.utcnow().isoformat()
                })
            )
            
            return jsonify({'status': 'success'}), 200
            
        except Exception as e:
            span.record_exception(e)
            logger.error(f"Feedback submission failed: {str(e)}")
            return jsonify({'error': 'Failed to submit feedback'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')