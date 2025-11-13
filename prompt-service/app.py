from flask import Flask, request, jsonify
from flask_cors import CORS
import redis
import json
import random
import hashlib
import re
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
    """Randomly select word count and corresponding difficulty with weighted probabilities"""
    import random
    
    # Options with (word_count, difficulty, weight)
    # Very Easy: 30%, Easy: 30%, Medium: 25%, Hard: 15%
    options = [
        (250, 'Very Easy', 30),
        (500, 'Easy', 30),
        (750, 'Medium', 25),
        (1000, 'Hard', 15)
    ]
    
    # Extract choices and weights
    choices = [(wc, diff) for wc, diff, _ in options]
    weights = [weight for _, _, weight in options]
    
    # Use random.choices for weighted selection
    word_count, difficulty = random.choices(choices, weights=weights, k=1)[0]
    return word_count, difficulty


def sanitize_ai_content(content):
    """Sanitize AI-generated content to remove garbled text and corruption"""
    if not content:
        return None
    
    import unicodedata
    
    # Remove control characters except newlines, carriage returns, and tabs
    content = ''.join(char for char in content if unicodedata.category(char)[0] != 'C' or char in '\n\r\t')
    
    # Detect and remove corrupted lines
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        
        # Skip empty lines (but preserve them for formatting)
        if not stripped_line:
            cleaned_lines.append(line)
            continue
        
        # Count various corruption indicators
        hex_escapes = len(re.findall(r'\\\\x[0-9A-Fa-f]', line))
        html_tags = len(re.findall(r'<[^>]*>', line))
        protocols = len(re.findall(r'(file://|ftp://|hidden_params|innerHTML|getElementById)', line))
        blocks = len(re.findall(r'[█▓▒░]', line))
        punct_clusters = len(re.findall(r'[!@#$%^&*()+={}\[\]|\\:;"<>?,./]{5,}', line))
        code_patterns = len(re.findall(r'(\$\(|\.entrySet\(|@@|[µ°†Δφε☐])', line))
        
        # Calculate corruption score
        corruption_score = hex_escapes * 3 + html_tags * 2 + protocols * 5 + blocks * 3 + punct_clusters * 2 + code_patterns * 3
        
        # If corruption score is too high, skip the line
        if len(stripped_line) > 10 and corruption_score > len(stripped_line) * 0.2:
            logger.warning(f"[SANITIZE] Skipping corrupted line: {stripped_line[:80]}")
            continue
        
        # If line starts with suspicious patterns, skip it
        if re.match(r'^\s*[.=]="<|^\s*[{\[][@$]|^\s*\\x', line):
            logger.warning(f"[SANITIZE] Skipping suspicious line: {stripped_line[:80]}")
            continue
        
        # Clean up remaining minor issues
        line = re.sub(r'\\\\x[0-9A-Fa-f]{2}', '', line)
        line = re.sub(r'[█▓▒░]+', '', line)
        line = re.sub(r'\\\\u[0-9A-Fa-f]{4}', '', line)
        
        cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Final validation: Check if remaining content is mostly printable
    if len(content) > 50:
        printable_ratio = sum(1 for c in content if c.isprintable() or c in '\n\r\t') / len(content)
        if printable_ratio < 0.85:
            logger.error(f"[SANITIZE] Content failed printability check ({printable_ratio:.2%}), returning None")
            return None

    # Check for semantic corruption patterns (word salad, incoherent text)
    # Look for lines with excessive capitalized words in sequence (likely corruption)
    for line in content.split('\n'):
        # Skip title lines and headers - they naturally have capitalized words
        if line.strip().startswith(('Title:', 'Step', '##', '#', '**', '-')):
            continue

        words = line.split()
        if len(words) > 15:  # Only check longer lines
            # Count consecutive capitalized words (excluding proper sentence starts)
            cap_sequences = []
            current_seq = 0
            for i, word in enumerate(words):
                # Skip first word of sentence and common capitalized terms
                clean_word = word.strip('.,;:!?()[]')
                if i > 0 and len(clean_word) > 1 and clean_word[0].isupper():
                    # Skip if it looks like a known proper noun pattern (artist/synth names)
                    if not any(keyword in clean_word for keyword in ['Serum', 'Phase', 'Plant', 'Vital', 'FM', 'LFO']):
                        current_seq += 1
                    else:
                        current_seq = 0
                else:
                    if current_seq >= 8:  # 8+ consecutive capitalized words is very suspicious
                        cap_sequences.append(current_seq)
                    current_seq = 0

            # Check the final sequence
            if current_seq >= 8:
                cap_sequences.append(current_seq)

            if cap_sequences and max(cap_sequences) >= 8:
                logger.warning(f"[SANITIZE] Detected suspicious capitalization pattern (word salad): {line[:100]}")
                return None

    return content.strip()

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
    """Generate creative writing exercises focused on skill-building"""
    import random
    import re
    
    genre_string = ", ".join(genres)
    
    exercise_types = [
        {
            "name": "Idea Generation Drill",
            "prompt": f"""Create an idea generation exercise for {genre_string} writing. 

Format:
**Exercise Name**: [Creative name]
**Goal**: [One sentence - what skill this develops]
**Exercise**: [Clear instructions explaining the drill]
**Example Progression**: [Show 3 examples from simple to unusual]
**Pro Tip**: [One sentence advice]

At the end, add a section:
**Writing Tips for This Exercise**:
- [Tip 1 specific to this exercise]
- [Tip 2 specific to this exercise]  
- [Tip 3 specific to this exercise]

NO character names. Focus on the TECHNIQUE of generating ideas."""
        },
        {
            "name": "World-Building Technique",
            "prompt": f"""Create a world-building exercise for {genre_string}.

Format:
**Technique Name**: [Name]
**Goal**: [What this teaches]
**Exercise**: [Instructions for the technique, 200-250 words]
**Rules**:
- [What to do]
- [What to avoid]
**Example Approach**: [2-3 sentences showing the METHOD]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 specific to world-building technique]
- [Tip 2 specific to world-building technique]
- [Tip 3 specific to world-building technique]

NO character names. Teach the CRAFT."""
        },
        {
            "name": "Structural Exercise",
            "prompt": f"""Create a structural writing exercise for {genre_string}.

Format:
**Structure Technique**: [Name]
**Goal**: [What this teaches about story structure]
**The Exercise**: [Explain the structural technique]
**Rules**: [Structural constraints and what they teach]
**Application**: [How to apply in 500 words]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about story structure]
- [Tip 2 about story structure]
- [Tip 3 about story structure]

Focus on STRUCTURE and TECHNIQUE."""
        },
        {
            "name": "Description Technique",
            "prompt": f"""Create a descriptive writing exercise for {genre_string}.

Format:
**Description Technique**: [Name]
**Goal**: [What skill this builds]
**The Challenge**: [Explain the descriptive technique]
**Requirements**:
- [Technical requirement 1]
- [Technical requirement 2]
- [Word count: 300-400 words]
**Forbidden**: [Generic words/habits to avoid]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about descriptive writing]
- [Tip 2 about descriptive writing]
- [Tip 3 about descriptive writing]

Teach CRAFT of description."""
        },
        {
            "name": "Dialogue Craft",
            "prompt": f"""Create a dialogue craft exercise for {genre_string}.

Format:
**Dialogue Technique**: [Name]
**Goal**: [What this teaches about dialogue]
**The Exercise**: [Instructions on HOW to write dialogue]
**What Dialogue Should Reveal**: [3 elements]
**Technical Rules**: [2 dialogue rules]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about dialogue craft]
- [Tip 2 about dialogue craft]
- [Tip 3 about dialogue craft]

Focus on dialogue CRAFT."""
        },
        {
            "name": "Theme & Subtext",
            "prompt": f"""Create a theme/subtext exercise for {genre_string}.

Format:
**Exercise Name**: [Name]
**Goal**: [What this teaches about theme]
**The Challenge**: [How to embed theme without preaching]
**Approach**: [2-3 techniques for showing theme]
**Practice**: [How to practice this skill in 300-500 words]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about theme and subtext]
- [Tip 2 about theme and subtext]
- [Tip 3 about theme and subtext]

Teach TECHNIQUE of thematic writing."""
        },
        {
            "name": "Genre Convention Study",
            "prompt": f"""Create a genre study exercise for {genre_string}.

Format:
**Genre Exercise**: [Name]
**Goal**: [What this teaches about genre craft]
**The Exercise**: [Instructions for working with genre conventions]
**Genre Mashup Option**: [How to combine {genre_string} with another genre]
**What You'll Learn**: [2 skills]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about genre conventions]
- [Tip 2 about genre conventions]
- [Tip 3 about genre conventions]

Focus on GENRE as craft tool."""
        },
        {
            "name": "Reverse Engineering",
            "prompt": f"""Create a reverse engineering exercise for {genre_string}.

Format:
**Analysis Exercise**: [Name]
**Goal**: [What this teaches about story construction]
**The Exercise**: Pick a {genre_string} story you admire. Analyze:
- [Element 1 to outline]
- [Element 2 to outline]
- [Element 3 to outline]
- [Element 4 to outline]
**Then**: [What to do with this analysis]
**What You'll Learn**: [The technique this reveals]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about analyzing stories]
- [Tip 2 about analyzing stories]
- [Tip 3 about analyzing stories]

Teach ANALYTICAL skills."""
        },
        {
            "name": "Constraint Creativity",
            "prompt": f"""Create a constraint-based exercise for {genre_string}.

Format:
**Constraint Exercise**: [Name]
**Goal**: [What this constraint teaches]
**The Constraint**: [Specific limitation and why it's useful]
**How to Apply It**: [Instructions for using this constraint in 500-750 words]
**What This Teaches**: [The craft skill forced by this constraint]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about working with constraints]
- [Tip 2 about working with constraints]
- [Tip 3 about working with constraints]

Focus on constraints as LEARNING TOOLS."""
        },
        {
            "name": "Revision Technique",
            "prompt": f"""Create a revision exercise for {genre_string}.

Format:
**Revision Technique**: [Name]
**Goal**: [What editing skill this builds]
**The Exercise**: Take any draft and apply this technique:
[Specific revision approach step-by-step]
**What to Look For**: [3 red flags]
**The Fix**: [How to revise each issue]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about revision and editing]
- [Tip 2 about revision and editing]
- [Tip 3 about revision and editing]

Teach REVISION as craft skill."""
        }
    ]
    
    exercise_type = random.choice(exercise_types)
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a creative writing instructor teaching techniques and skills. Create exercises that are instructional and teach craft, not story prompts. Avoid character names and specific scenarios. Focus on teaching HOW to write. Always include 3 specific writing tips tailored to the exercise."},
                {"role": "user", "content": exercise_type["prompt"]}
            ],
            temperature=0.85,
            max_tokens=800,
            presence_penalty=0.7,
            frequency_penalty=0.7
        )
        
        content = response.choices[0].message.content
        
        # Extract title
        title = None
        lines = content.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line.startswith('**') or line.startswith('#'):
                title = line.replace('**', '').replace('#', '').strip()
                if title and len(title) > 3 and len(title) < 100:
                    break
        
        if not title:
            title = f"{exercise_type['name']}: {genre_string}"
        
        # Extract writing tips from the content
        tips = []
        content_without_tips = content
        
        # Find the "Writing Tips" section
        tip_section_match = re.search(r'\*\*Writing Tips.*?\*\*:?\s*\n(.*?)(?=\n\n|\Z)', content, re.DOTALL | re.IGNORECASE)
        
        if tip_section_match:
            tip_section = tip_section_match.group(1)
            
            # Extract individual tips
            for line in tip_section.split('\n'):
                line = line.strip()
                if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                    tip = re.sub(r'^[-•*]\s*', '', line).strip()
                    if tip and len(tip) > 10:
                        tips.append(tip)
            
            # Remove the entire "Writing Tips" section from content
            content_without_tips = re.sub(r'\*\*Writing Tips.*?\*\*:?\s*\n.*?(?=\n\n|\Z)', '', content, flags=re.DOTALL | re.IGNORECASE)
            content_without_tips = content_without_tips.strip()
        
        # Fallback to generic tips if none found
        if not tips:
            tips = [
                f"Practice this exercise regularly to build muscle memory for {exercise_type['name'].lower()}",
                "Don't edit while doing the exercise - focus on exploration first",
                "Review your work after completing the exercise to identify patterns"
            ]
        
        word_count, difficulty = get_random_word_count_and_difficulty()
        
        return {
            'title': title,
            'content': content_without_tips,  # Content WITHOUT the tips section
            'genres': genres,
            'difficulty': difficulty,
            'wordCount': word_count,
            'exerciseType': exercise_type['name'],
            'tips': tips[:3],  # Tips extracted separately, only first 3
            'timestamp': datetime.utcnow().isoformat(),
            'ai_generated': True
        }
    except Exception as e:
        logger.error(f"AI generation failed: {str(e)}")
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

def generate_sound_design_prompt(synthesizer, exercise_type, genre="all"):
    """Generate sound design exercises for electronic music production"""

    # Synthesizer capabilities and context
    synth_context = {
        'Serum 2': {
            'type': 'wavetable',
            'features': 'advanced modulation matrix, visual feedback, effects rack, wavetable editor',
            'strengths': 'complex modulation routing, visual waveform manipulation, FM synthesis'
        },
        'Phase Plant': {
            'type': 'modular',
            'features': 'snapin effects, flexible routing, multiple oscillator types',
            'strengths': 'modular signal flow, creative effects combinations, harmonic oscillators'
        },
        'Vital': {
            'type': 'wavetable',
            'features': 'spectral warping, advanced modulation, free and open-source',
            'strengths': 'spectral effects, stereo modulation, filter morphing'
        }
    }

    # Book tracking for even distribution (creative/abstract exercises only)
    all_books = [
        'Red Rising', 'The Left Hand of Darkness', "Ender's Game", 'Station Eleven', 'The Peripheral',
        'Neuromancer', 'The Goldfinch', "The Hitchhiker's Guide", 'The Kite Runner', 'Borne',
        'Dark Matter', 'The Illustrated Man', 'Recursion', 'The City & the City', 'Mistborn',
        'A Memory Called Empire', 'The Three-Body Problem', 'Fahrenheit 451', 'The Nightingale',
        'The House in the Cerulean Sea', 'Dune', 'Annihilation', 'Upgrade', 'Wayward Pines',
        'The Martian', 'Cloud Atlas', 'The Woman in White', 'Foundation', 'Snow Crash',
        'The Long Way to a Small, Angry Planet', 'Frankenstein', 'American Gods', '1984',
        'The Hunger Games', 'Nexus', 'The Mountain in the Sea', 'Scythe', 'Watchmen', 'Dorohedoro',
        "Howl's Moving Castle", 'Eragon', 'The Girl on the Train', 'The Silkworm', 'The Night Fire',
        'Lock In', 'The Night Manager', 'The Van Apfel Girls Are Gone', 'The Lord of the Rings',
        'A Song of Ice and Fire', 'The Name of the Wind', 'Elantris', 'The Way of Kings',
        'The Once and Future King', 'The Chronicles of Narnia', 'The Wheel of Time', 'The Hobbit',
        'The Time Machine', 'The Invisible Man', 'Dracula', 'Brave New World', 'The Hollow Crown',
        'The Stars My Destination', 'The Caves of Steel', 'Extremity', 'Katabasis'
    ]

    # Artist tracking for even distribution (technical exercises only)
    # Organized by genre for filtering
    artists_by_genre = {
        'dubstep': [
            'Eptic', 'Must Die!', 'Monty', 'Skrillex', 'Virtual Riot', 'Space Laces', 'Excision', 'Zeds Dead', 'Flux Pavilion', 'Subtronics', 'Knife Party', 'Kompany', 'Zomboy', 'Rusko',
            'Borgore', 'Downlink', 'Noisestorm', 'Spag Heddy', 'Kayzo', 'Kode9', 'Kill the Noise', 'Kahn', 'Liquid Stranger', 'Truth'
        ],
        'glitch-hop': [
            'Detox Unit', 'Seppa', 'Kursa', 'Koan Sound', 'Resonant Language', 'Tipper', 'The Glitch Mob', 'Opiuo', 'Gramatik', 'Haywyre', 'CloZee', 'The Polish Ambassador', 'Beats Antique',
            'Random Rab', 'Glacier', 'Echo Map', 'Complexive', 'rabidZen', 'Two Fingers', 'Hudson Mohawke', 'Juno What', 'ill.Gates', 'Paper Tiger'
        ],
        'dnb': [
            'Noisia', 'Sleepnet', 'Broken Note', 'Clockvice', 'Vorso', 'Alix Perez', 'Simula', 'Culprate', 'Goldie', 'LTJ Bukem', 'Andy C', 'Roni Size', 'Chase & Status', 'Sub Focus', 'Netsky', 'High Contrast', 'Pendulum', 'Dimension',
            'Hedex', 'Irah', 'Trigga', 'Bou', 'K-Motionz', 'DJ Fresh', 'Black Sun Empire', 'Calibre', 'Phantasm', 'Metrik'
        ],
        'experimental-bass': [
            'Mr. Bill', 'Tiedye Ky', 'Lab Group', 'Supertask', 'Esseks', 'Charlesthefirst', 'Mr. Carmack', 'Tsuruda', 'Chee', 'Flying Lotus', 'G Jones', 'Eprom', 'Of The Trees', 'Mersiv', 'Khiva', 'Templo', 'Risik', 'Seven Orbits', 'Abstrakt Sonance',
            'Duke & Jones', 'Cozway', 'Jeanie', 'Razat', 'Roxas & Klahrk', 'Toadface', 'Sapped', 'Tsimba', 'DMVU', 'SLAVE'
        ],
        'house': [
            'Tchami', 'Chris Lorenzo', 'Daft Punk', 'Larry Heard', 'Masters At Work', 'Derrick Carter', 'DJ Sneak', 'FISHER', 'John Summit', 'Joel Corry', 'Bob Sinclar', 'CID',
            'BLOND:ISH', 'Noizu', 'Dom Dolla', 'Malaa', 'Wax Motif', 'Kaskade', 'Marten Hørger', 'Afrojack', 'Tiësto', 'Black Coffee'
        ],
        'psytrance': [
            'Astrix', 'Vini Vici', 'Infected Mushroom', 'Liquid Soul', 'GMS', 'Ace Ventura', 'Hallucinogen', 'Electric Universe', 'Zen Mechanics', 'Avalon',
            'Indira Paganotto', 'Phaxe', 'Morten Granau', 'Killerwatts', 'Outsiders', 'X-Noize', 'Blastoyz', 'Relativ', 'Faders', 'Tristan'
        ],
        'hard-techno': [
            'Ihatemodels', 'Sara Landry', 'Charlotte De Witte', 'Kobosil', 'Rephate', 'WNDRLST', 'In Verruf', 'Madwoman', 'Nicolas Julian', 'Helena Hauff', 'Alignment', 'Kozlov',
            'Victor Ruiz', 'Layton Giordani', 'Bart Skils', 'Sven Väth', 'Paul Kalkbrenner', 'Stephan Bodzin', 'Peggy Gou', 'HI-LO', 'Space 92', 'Eli Brown'
        ]
    }
    
    # Create all_artists list from all genres
    all_artists = []
    for genre_artists in artists_by_genre.values():
        all_artists.extend(genre_artists)

    # Define fallback templates (used both when USE_AI is False and as fallback in exception handlers)
    if exercise_type == 'technical':
        templates = {
            'Serum 2': [
                    "Create a Skrillex-style metallic bass using FM modulation with detuned oscillators and harsh filtering",
                    "Design a Virtual Riot supersized growl with heavy unison (8+ voices), movement automation, and vowel-like filter morphing",
                    "Build a Space Laces glitchy lead with rapid wavetable morphing, chaos modulation, and pitch shifting",
                    "Create a Tchami future house bass using filtered square waves with punchy envelope and subtle pitch modulation",
                    "Design a G Jones experimental texture using custom wavetables, extreme modulation routing, and unconventional LFO rates",
                    "Build a Chee-style neuro bass with complex FM routing, filter drive saturation, and rhythmic modulation",
                    "Create a Resonant Language organic lead using evolving wavetables, subtle detuning, and harmonic filtering",
                    "Design a Noisia reese bass with multiple detuned saw waves, precise filter automation, and subtle movement",
                    "Build an Eptic heavy riddim bass using square wave FM, aggressive filtering, and pitch envelope modulation",
                    "Create an Esseks wonky mid-bass with wavetable morphing, stereo movement, and creative modulation routing",
                    "Design a Mr. Bill glitchy texture using rapid wavetable scanning, micro-modulation, and rhythmic gating",
                    "Build a Charlesthefirst melodic bass using warm wavetables, filter movement, and subtle portamento"
                ],
                'Phase Plant': [
                    "Create an Eprom heavy bass using layered oscillators with distortion snapins and parallel processing chains",
                    "Design a Tipper-style surgical bass with modular signal flow, precise filter automation, and subtle harmonic movement",
                    "Build a Culprate atmospheric texture combining multiple oscillator types with creative snapin effect routing",
                    "Create a Koan Sound neurofunk bass using harmonic oscillators, modular routing, and aggressive distortion staging",
                    "Design a Kursa experimental sound using non-standard oscillator combinations and unconventional effect chains",
                    "Build a Seppa downtempo lead with smooth oscillator blending, modular filter routing, and spatial effects",
                    "Create a Vorso glitch bass using granular-style oscillator manipulation and complex modulation matrices",
                    "Design a Noisia neurofunk reese with parallel oscillator processing, multiband distortion, and stereo width control",
                    "Build a Sleepnet heavy techno bass using analog oscillators, aggressive snapin chains, and movement automation",
                    "Create a Broken Note industrial sound with noise oscillators, distortion routing, and modular signal flow",
                    "Design a Clockvice neurohop bass using oscillator layering, creative snapin routing, and precise automation",
                    "Build a Detox Unit experimental bass with unconventional oscillator combinations and chaotic modulation matrices"
                ],
                'Vital': [
                    "Create an Alix Perez deep bass using spectral warping on sine waves with subtle harmonic enhancement",
                    "Design a Flying Lotus experimental lead using spectral effects, filter morphing, and stereo width modulation",
                    "Build a Tsuruda wonky bass with filter drive, spectral warping, and unconventional pitch modulation",
                    "Create a Mr. Carmack trap lead using saw waves with stereo spreading, filter movement, and distortion",
                    "Design a Monty future bass sound with bright wavetables, stereo modulation, and spectral processing",
                    "Build a Chris Lorenzo bassline house bass using filtered saws, punchy envelopes, and subtle distortion warmth",
                    "Create a Simula atmospheric pad using spectral warping, slow filter morphing, and wide stereo field",
                    "Design an Ihatemodels hard techno kick-bass using sine waves with spectral distortion and pitch envelope",
                    "Build a Sara Landry techno lead using spectral warping, stereo modulation, and filter drive",
                    "Create a Must Die! heavy bass using spectral effects, aggressive filtering, and movement automation",
                    "Design a Tiedye Ky melodic bass with spectral warping, filter morphing, and stereo width",
                    "Build a Lab Group experimental sound using spectral processing, LFO modulation, and filter movement",
                    "Create a Supertask neuro bass with spectral warping, precise filter automation, and stereo enhancement"
                ]
        }
    else:  # creative/abstract
        templates = {
            'Serum 2': [
                    "**Translation**: The razor rain on Mars in Red Rising—glass shards falling from the sky. Create the sound of that descent. Not the impact, the falling. How does danger sound when it's beautiful? | Work until it cuts.",
                    "**Context Shift**: In The Left Hand of Darkness, winter never ends. Design a bass that exists in permanent twilight, where warmth is a memory and cold has texture. What does glacial time sound like? | Begin from not knowing.",
                    "**Synesthesia**: The ansible from Ender's Game—instantaneous communication across light-years. Create the sound of a message that arrives before it's sent. Backwards causality as tone. | Stop when time breaks.",
                    "**Awareness**: In Station Eleven, the traveling symphony performs Shakespeare after civilization ends. Design the sound of culture persisting through collapse. Fragile but unbreakable. | Trust what emerges.",
                    "**Accident**: The reality overlay in The Peripheral—two timelines bleeding through each other. Randomize your routing. Let two patches exist in the same space. Don't resolve the paradox. | Follow what excites you.",
                    "**Limitation**: Neuromancer's cyberspace, built from pure data. Use only one oscillator and one filter. What can consciousness sound like when stripped to its simplest form? | Begin from not knowing.",
                    "**Discovery**: The Goldfinch painting—how Theo sees the world through it. Cycle through wavetables until one makes you feel something you can't name. Build from that unnameable thing. | Work intuitively.",
                    "**Play**: In The Hitchhiker's Guide, Earth is demolished for a hyperspace bypass. Create the bureaucratic sound of a planet being deleted. Absurd. Mundane. Catastrophic. | 5 minutes or until you laugh.",
                    "**Context Shift**: The kites in The Kite Runner—freedom and guilt tangled together. Design a lead that climbs and falls. What does redemption sound like when it's too late? | Work until it aches.",
                    "**Translation**: Borne by Vandermeer—a biotech creature that defies categories. Design something that shouldn't be alive but is. What does impossible biology sound like? | Follow what excites you.",
                    "**Awareness**: Dark Matter's box—every choice creates a new universe. Create a tone. Then modulate it. Each tweak is a branching world. Which path do you follow? | Trust what emerges.",
                    "**Synesthesia**: The Illustrated Man's living tattoos—stories written on skin. Build a patch where every parameter tells a different tale. What does illustrated sound look like? | Work intuitively.",
                    "**Discovery**: Recursion's memory chairs—you can relive any moment. Cycle through presets until one feels like a memory you never had. Build from false nostalgia. | Begin from not knowing."
                ],
                'Phase Plant': [
                    "**Awareness**: The split cities in The City & the City—two places occupying the same space, each unseeing the other. Build a bass where two layers coexist but never touch. Parallel sonic realities. | Work until the energy shifts.",
                    "**Translation**: Allomancy in Mistborn—burning metals to push and pull on the world. Create sound that feels like telekinesis. Physical force at a distance. Choose snapins that push or pull. | Stop when it feels right.",
                    "**Limitation**: The Memory of Empire—a diplomat in a foreign court where every word is strategy. Build using only snapin effects, no oscillators. Politics as pure modulation. | Trust the process.",
                    "**Accident**: The ansible in A Memory Called Empire—cultural memory downloaded directly into the mind. Route modulation randomly to six destinations. Don't undo. Let foreign memories guide you. | Follow what excites you.",
                    "**Discovery**: The Three-Body Problem's chaotic eras—unpredictable swings between stability and disaster. Chain three random snapins. Find five sounds. Notice which ones feel like home, which like catastrophe. | Explore freely.",
                    "**Context Shift**: In Fahrenheit 451, books are burned and firemen start fires. Create a lead that's both destroyer and preserver. What burns? What survives? | Work until complete.",
                    "**Synesthesia**: The Nightingale's two sisters—one brave, one invisible, both essential. Design drums with two voices. One urgent, one patient. Both necessary. | Follow your intuition.",
                    "**Play**: The House in the Cerulean Sea—magical children in bureaucratic care. Design something that shouldn't work but does. Rules broken gently. | 5 minutes maximum.",
                    "**Translation**: The spice melange in Dune—awareness expanding across time. Design a texture that seems to know what's coming. Prescient sound. | Open-ended exploration.",
                    "**Context Shift**: Annihilation's Area X—where nature rewrites the rules. Layer oscillators that mutate each other. Let biology become architecture. What does transformation sound like? | Stop when it feels right.",
                    "**Awareness**: Upgrade's gene-editing plague—becoming more and less human simultaneously. Build a patch that improves as it degrades. Enhancement as loss. | Work until the energy shifts.",
                    "**Accident**: Wayward Pines' town—perfect prison disguised as paradise. Route modulation to hidden destinations. Surface order, underlying chaos. What looks safe but isn't? | Follow what excites you.",
                    "**Discovery**: The Martian's survival math—solving impossible problems with duct tape and cleverness. Chain random snapins. Make them work through pure problem-solving. | Explore freely."
                ],
                'Vital': [
                    "**Discovery**: In Cloud Atlas, six stories echo across time. Set a filter to self-oscillate. Now treat it as an oscillator. The roles flip. The echo becomes the source. | Explore until complete.",
                    "**Translation**: The Woman in White—a figure glimpsed at midnight, impossible to forget. Create a pad that haunts the edges. Present but not quite there. Victorian dread. | Work as slowly as shadows move.",
                    "**Limitation**: Foundation's psychohistory—predicting civilization with one equation. Use only one LFO to modulate everything. One source, infinite outcomes. What patterns emerge? | Embrace what appears.",
                    "**Accident**: Snow Crash's metaverse—digital religion as computer virus. Enable spectral warping. Drag randomly. Don't look. Let the infection spread through sound. | Stop when it feels alive.",
                    "**Context Shift**: The Long Way to a Small, Angry Planet—found family in deep space. Design a sound at atomic scale. When you're small enough, loneliness feels different. | Work until the perspective shifts.",
                    "**Synesthesia**: Frankenstein's creature—assembled from pieces, alive despite impossibility. What does unnatural life sound like? Not horror. Tragedy. | Open-ended exploration.",
                    "**Play**: American Gods—old deities working at gas stations. Design something ancient trying to be modern. Mythology in fluorescent light. Absurd displacement. | 5 minutes of pure play.",
                    "**Awareness**: 1984's memory holes—history erased in real-time. Create a lead that forgets itself as it plays. What remains when the recording is deleted? | Let the sound tell you.",
                    "**Translation**: The Hunger Games' mockingjay—rebellion encoded in birdsong. Spectral warp a simple tone until it carries a message it doesn't understand. | Begin from not knowing.",
                    "**Synesthesia**: Nexus nano-drug—thoughts transmitted between minds. Create spectral movement that feels like telepathy. Direct consciousness transfer as filter sweep. | Stop when it feels alive.",
                    "**Context Shift**: The Mountain in the Sea's octopus language—intelligence that doesn't think like us. Design at alien scale. What does non-human thought sound like? | Work until the perspective shifts.",
                    "**Play**: Scythe's immortal world—where death is a profession. Make something beautiful about endings. Mortality as melody. | 5 minutes of pure play.",
                    "**Awareness**: Watchmen's Dr. Manhattan—experiencing all time simultaneously. Create a lead that plays past, present, future at once. Omnitemporality as tone. | Let the sound tell you.",
                    "**Translation**: Dorohedoro's magic smoke—it transforms what it touches. Spectral warp until identity dissolves. What does shapeshifting sound like? | Begin from not knowing."
                ]
            }


    if not USE_AI:
        content = random.choice(templates.get(synthesizer, templates['Serum 2']))
        title = f"{exercise_type.capitalize()} Sound Design Exercise"

        if exercise_type == 'technical':
            tips = [
                "Start with initializing the synth to hear your changes clearly",
                "Use your ears - trust what sounds good rather than just visual feedback",
                "Save variations as you go to compare different approaches"
            ]
        else:  # creative/abstract
            tips = [
                "There is no destination, only discovery. Follow what makes you curious",
                "If you're overthinking, you're not playing. Trust your first instinct",
                "The 'mistake' that excites you is the exercise working",
                "Stop when the energy shifts. Not everything needs finishing",
                "Your ears know more than your eyes. Close the screen if it helps",
                "If nothing excites you after 5 minutes, start completely over",
                "The exercise is in the noticing, not the result"
            ]
            tips = random.sample(tips, 3)  # Pick 3 random tips
    else:
        # AI-generated sound design prompts
        synth_info = synth_context.get(synthesizer, synth_context['Serum 2'])

        if exercise_type == 'technical':
            # Get next artist from rotation to ensure even distribution
            # Filter artists by selected genre
            logger.info(f"[GENRE DEBUG] Received genre parameter: {genre}")

            if genre == 'all':
                artist_pool = all_artists
                redis_key = 'sound_design:artist_rotation_index:all'
                logger.info(f"[GENRE DEBUG] Using 'all' pool with {len(artist_pool)} artists")
            else:
                # Map frontend genre values to backend genre keys
                genre_map = {
                    'dubstep': 'dubstep',
                    'glitch-hop': 'glitch-hop',
                    'dnb': 'dnb',
                    'experimental-bass': 'experimental-bass',
                    'house': 'house',
                    'psytrance': 'psytrance',
                    'hard-techno': 'hard-techno'
                }

                backend_genre = genre_map.get(genre, 'all')
                logger.info(f"[GENRE DEBUG] Mapped frontend genre '{genre}' to backend genre '{backend_genre}'")

                if backend_genre in artists_by_genre:
                    artist_pool = artists_by_genre[backend_genre]
                    logger.info(f"[GENRE DEBUG] Found genre pool for '{backend_genre}' with {len(artist_pool)} artists")
                    logger.info(f"[GENRE DEBUG] First 5 artists: {artist_pool[:5]}")
                else:
                    artist_pool = all_artists
                    logger.info(f"[GENRE DEBUG] Genre '{backend_genre}' not found, using all_artists")

                redis_key = f'sound_design:artist_rotation_index:{backend_genre}'

            logger.info(f"[GENRE DEBUG] Redis key: {redis_key}")

            try:
                # Get the shuffled artist order and current position from Redis
                shuffled_key = f'{redis_key}:shuffled'
                position_key = f'{redis_key}:position'

                # Get current shuffled order
                shuffled_indices = redis_client.get(shuffled_key)

                if shuffled_indices is None:
                    # First time for this genre - create a shuffled list of indices
                    indices = list(range(len(artist_pool)))
                    random.shuffle(indices)
                    redis_client.set(shuffled_key, json.dumps(indices))
                    redis_client.set(position_key, 0)
                    shuffled_indices = indices
                    current_position = 0
                    logger.info(f"[GENRE DEBUG] Created new shuffled order for {backend_genre}")
                else:
                    # Parse the shuffled order from JSON
                    shuffled_indices = json.loads(shuffled_indices)
                    current_position = int(redis_client.get(position_key) or 0)

                    # If we've gone through all artists, reshuffle for next cycle
                    if current_position >= len(shuffled_indices):
                        indices = list(range(len(artist_pool)))
                        random.shuffle(indices)
                        redis_client.set(shuffled_key, json.dumps(indices))
                        redis_client.set(position_key, 0)
                        shuffled_indices = indices
                        current_position = 0
                        logger.info(f"[GENRE DEBUG] Reshuffled artist order for {backend_genre}")

                logger.info(f"[GENRE DEBUG] Current position in shuffled list: {current_position}")

                # Get the artist at the current shuffled position
                artist_index = shuffled_indices[current_position]
                selected_artist = artist_pool[artist_index]
                logger.info(f"[GENRE DEBUG] Selected artist: {selected_artist} (index {artist_index})")

                # Increment position for next time
                redis_client.set(position_key, current_position + 1)

            except Exception as e:
                logger.error(f"Error with artist rotation: {str(e)}")
                # Fallback to random selection
                selected_artist = random.choice(artist_pool)

            system_prompt = f"""You are an expert sound designer and educator specializing in {synthesizer}.
{synthesizer} is a {synth_info['type']} synthesizer with {synth_info['features']}.
It excels at {synth_info['strengths']}.

IMPORTANT: You MUST base this exercise on the artist "{selected_artist}". Create a technical exercise that teaches their signature sound design techniques.

Available artists for context (but focus on {selected_artist}): All genres from Dubstep, Glitch Hop, Drum and Bass, Experimental Bass, House, Psytrance, and Hard Techno including artists like Skrillex, Virtual Riot, Noisia, KOAN Sound, Alix Perez, Daft Punk, Infected Mushroom, Charlotte De Witte, and many more.

The exercise should:
1. Reference {selected_artist}'s specific signature sound style
2. Provide step-by-step technical guidance using {synthesizer}'s specific features
3. Detail synthesis parameters (oscillators, filters, modulation, effects)
4. Include tips for achieving {selected_artist}'s characteristic production techniques

Keep instructions clear and actionable, referencing {synthesizer}'s actual interface elements.
Examples: "Create a Skrillex-style metallic bass", "Design a Tipper surgical bass", "Build a Virtual Riot supersized growl"."""

            user_prompt = f"Create a technical sound design exercise based on {selected_artist}'s signature sounds, with step-by-step synthesis instructions specific to their production style."

        else:  # creative/abstract
            # Get next book from rotation to ensure even distribution
            try:
                # Get the current book index from Redis
                book_index_key = 'sound_design:book_rotation_index'
                current_index = redis_client.get(book_index_key)

                if current_index is None:
                    current_index = 0
                else:
                    current_index = int(current_index)

                # Get the next book
                selected_book = all_books[current_index % len(all_books)]

                # Increment the index for next time
                redis_client.set(book_index_key, (current_index + 1) % len(all_books))

            except Exception as e:
                logger.error(f"Error with book rotation: {str(e)}")
                # Fallback to random selection
                selected_book = random.choice(all_books)

            system_prompt = f"""You are a creative companion for sound design. Create exercises for {synthesizer} that draw inspiration from literature—pulling in vivid imagery, emotional textures, and conceptual depth from novels.

{synthesizer} is a {synth_info['type']} synthesizer with {synth_info['features']}.

IMPORTANT: You MUST base this exercise on the book "{selected_book}". Reference specific concepts, imagery, or moments from this book.

Available books for reference (but use {selected_book} for this exercise): Neuromancer, Dune, The Left Hand of Darkness, Station Eleven, The Three-Body Problem, Red Rising, Mistborn, The City & the City, 1984, Fahrenheit 451, Cloud Atlas, American Gods, Snow Crash, The Peripheral, Foundation, Ender's Game, The Kite Runner, The Goldfinch, Frankenstein, The Hunger Games, The Woman in White, Borne, Annihilation, Dark Matter, Upgrade, Recursion, Wayward Pines, Nexus, The Illustrated Man, The Mountain in the Sea, Scythe, The Martian, Watchmen, Dorohedoro, Howl's Moving Castle, Eragon.

Exercise Types (choose one):
- **Translation**: Translating literary imagery or concepts into sound (the ansible, psychohistory, allomancy, etc.)
- **Context Shift**: Shifting perspective through a book's lens (cyberspace, split cities, eternal winter, post-apocalypse)
- **Limitation**: Constraints inspired by story elements (one equation, one metal, stripped consciousness)
- **Accident**: Embracing chaos through narrative concepts (timeline bleeding, cultural memory, viral spread)
- **Awareness**: Deep listening through a story's emotional core (collapse, persistence, displacement)
- **Synesthesia**: Literary concepts as sonic textures (rebellion as birdsong, danger as beauty, guilt as flight)
- **Play**: Absurdist or tragicomic concepts from stories (gods at gas stations, planets as paperwork)
- **Discovery**: Exploring inversions and paradoxes from narratives (echo as source, forgetting as creation)

Format like this:
**[Exercise Type]**: [Reference a specific book/concept]. [Main instruction—concrete, evocative, strange]. [Short poetic questions or observations]. | [Inviting end phrase]

IMPORTANT:
- Be specific with literary references—name the book, the concept, the image
- Make it feel literary, not generic ("razor rain on Mars" not "rain")
- Remove ALL judgment language
- Create emotional/conceptual depth, not just "make a spooky sound"
- Embrace paradox and complexity from the source material
- Suggest varied time frames: "5 minutes," "until it aches," "work until it cuts," "stop when time breaks"
- Let the exercise feel like play, not work"""

            user_prompt = f"Create a creative/abstract sound design exercise inspired by a specific moment, concept, or imagery from {selected_book}. Make it evocative and strange, not generic. You MUST reference {selected_book} by name in your exercise."

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=600,
                presence_penalty=0.3,
                frequency_penalty=0.3
            )

            content = response.choices[0].message.content.strip()
            
            # Sanitize the AI-generated content to remove corruption
            sanitized = sanitize_ai_content(content)
            if not sanitized:
                logger.error("[SANITIZE] Writing prompt content sanitization failed, using fallback")
                raise ValueError("Sanitized writing prompt content is invalid")
            content = sanitized
            
            # Sanitize the AI-generated content to remove corruption
            sanitized = sanitize_ai_content(content)
            if not sanitized:
                logger.error("[SANITIZE] Content sanitization failed, using fallback template")
                raise ValueError("Sanitized content is invalid")
            content = sanitized

            # Extract title if present
            lines = content.split('\n')
            if lines[0].startswith('#') or (len(lines[0]) < 60 and not lines[0].endswith('.')):
                title = lines[0].replace('#', '').strip()
                content = '\n'.join(lines[1:]).strip()
            else:
                title = f"{synthesizer} - {exercise_type.capitalize()} Exercise"

            # Extract tips
            tips = []
            tip_section_match = re.search(r'\*\*Tips.*?\*\*:?\s*\n(.*?)(?=\n\n|\Z)', content, re.DOTALL | re.IGNORECASE)
            if tip_section_match:
                tip_section = tip_section_match.group(1)
                for line in tip_section.split('\n'):
                    line = line.strip()
                    if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                        tip = re.sub(r'^[-•*]\s*', '', line).strip()
                        if tip and len(tip) > 10:
                            tips.append(tip)
                content = re.sub(r'\*\*Tips.*?\*\*:?\s*\n.*?(?=\n\n|\Z)', '', content, flags=re.DOTALL | re.IGNORECASE).strip()

            if not tips:
                if exercise_type == 'technical':
                    tips = [
                        "Reference tracks can help guide your sound design decisions",
                        "A/B test your patch in a mix context, not just solo",
                        "Document your process - you'll learn patterns in your workflow"
                    ]
                else:  # creative/abstract
                    tips = [
                        "There is no destination, only discovery. Follow what makes you curious",
                        "If you're overthinking, you're not playing. Trust your first instinct",
                        "The 'mistake' that excites you is the exercise working",
                        "Stop when the energy shifts. Not everything needs finishing",
                        "Your ears know more than your eyes. Close the screen if it helps",
                        "If nothing excites you after 5 minutes, start completely over",
                        "The exercise is in the noticing, not the result"
                    ]
                    tips = random.sample(tips, 3)

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            # Fallback to template
            content = random.choice(templates.get(synthesizer, templates['Serum 2']))
            title = f"{synthesizer} - {exercise_type.capitalize()} Exercise"
            tips = ["Experiment with modulation sources", "Layer multiple oscillators", "Use effects creatively"]

    # Determine difficulty and estimated time (matched pairs)
    difficulty_time_pairs = [
        ('Beginner', '15 minutes'),
        ('Intermediate', '30 minutes'),
        ('Expert', '45 minutes')
    ]

    difficulty, estimated_time = random.choice(difficulty_time_pairs)

    return {
        'title': title,
        'content': content,
        'synthesizer': synthesizer,
        'exerciseType': exercise_type,
        'difficulty': difficulty,
        'estimatedTime': estimated_time,
        'tips': tips[:3],
        'timestamp': datetime.utcnow().isoformat()
    }

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

@app.route('/generate-sound-design', methods=['POST'])
def generate_sound_design():
    """Generate a sound design exercise based on synthesizer and exercise type"""
    with tracer.start_as_current_span("generate-sound-design") as span:
        try:
            data = request.json
            synthesizer = data.get('synthesizer', 'Serum 2')
            exercise_type = data.get('exerciseType', 'technical')
            genre = data.get('genre', 'all')
            user_id = data.get('userId', 'anonymous')

            span.set_attribute("user.id", user_id)
            span.set_attribute("synthesizer", synthesizer)
            span.set_attribute("exercise.type", exercise_type)
            span.set_attribute("genre", genre)

            # Validate inputs
            valid_synths = ['Serum 2', 'Phase Plant', 'Vital']
            valid_types = ['technical', 'creative']
            valid_genres = ['all', 'dubstep', 'glitch-hop', 'dnb', 'experimental-bass', 'house', 'psytrance', 'hard-techno']

            if synthesizer not in valid_synths:
                return jsonify({'error': f'Invalid synthesizer. Must be one of: {", ".join(valid_synths)}'}), 400

            if exercise_type not in valid_types:
                return jsonify({'error': f'Invalid exercise type. Must be one of: {", ".join(valid_types)}'}), 400

            if genre not in valid_genres:
                return jsonify({'error': f'Invalid genre. Must be one of: {", ".join(valid_genres)}'}), 400

            # Generate prompt
            span.add_event("generating-sound-design-prompt")
            prompt = generate_sound_design_prompt(synthesizer, exercise_type, genre)

            # Track metrics
            span.set_attribute("prompt.title", prompt['title'])
            span.set_attribute("prompt.difficulty", prompt['difficulty'])
            span.set_attribute("prompt.estimated_time", prompt['estimatedTime'])

            return jsonify(prompt), 200

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Sound design prompt generation failed: {str(e)}")
            return jsonify({'error': 'Failed to generate sound design prompt'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')