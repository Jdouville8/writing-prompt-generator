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
from midiutil import MIDIFile
import io
import base64

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

# Emotion data for chord progression generation
EMOTIONS = [
    {
        "emotion": "Melancholy",
        "tonal_center": "A minor or D minor",
        "chord_colors": ["add9", "sus2", "minor7", "bVI", "bVII"],
        "notes_for_generation": "Use unresolved minor progressions with soft transitions. Avoid dominant resolutions. Think of fading memories or rain."
    },
    {
        "emotion": "Elation",
        "tonal_center": "C major or A Mixolydian",
        "chord_colors": ["major7", "add9", "IV → I", "Lydian #4"],
        "notes_for_generation": "Bright voicings, open fifths, layered synths. Capture upward momentum and emotional lift."
    },
    {
        "emotion": "Resentment",
        "tonal_center": "F minor or G Phrygian",
        "chord_colors": ["minor6", "dim7", "bII", "chromatic movement"],
        "notes_for_generation": "Dark tension, unresolved cadences, low mid emphasis. Use half-steps or harsh dissonance sparingly."
    },
    {
        "emotion": "Awe",
        "tonal_center": "D Lydian or E major",
        "chord_colors": ["maj7", "sus2", "add9", "pedal bass"],
        "notes_for_generation": "Massive spatial reverb, sustained chords, harmonic suspension. Feel of cosmic scale or vastness."
    },
    {
        "emotion": "Nostalgia",
        "tonal_center": "B♭ major or G minor",
        "chord_colors": ["major7", "6/9", "bVII", "borrowed iv"],
        "notes_for_generation": "Blend major and minor. Gentle filter sweeps or tape saturation evoke memory and warmth."
    },
    {
        "emotion": "Serenity",
        "tonal_center": "E major or A Lydian",
        "chord_colors": ["maj7", "add9", "sus4"],
        "notes_for_generation": "Open voicings, soft attack envelopes, slow movement. Prioritize harmonic stillness and consonance."
    },
    {
        "emotion": "Apprehension",
        "tonal_center": "C# Phrygian or D minor",
        "chord_colors": ["minor2", "bII", "dim7", "suspended movement"],
        "notes_for_generation": "Use tense intervals (minor 2nd, tritone), subtle pulsing bass, and unresolved transitions."
    },
    {
        "emotion": "Defiance",
        "tonal_center": "E minor or A Dorian",
        "chord_colors": ["power chords", "bVII", "sus4", "modal mix"],
        "notes_for_generation": "Use modal grit, syncopation, and strong rhythmic accents. Think proud, rebellious harmonic energy."
    },
    {
        "emotion": "Longing",
        "tonal_center": "F# minor or C# minor",
        "chord_colors": ["add9", "maj7", "minor11", "borrowed IV"],
        "notes_for_generation": "Open harmonic tension, melodic upper voices rising against static bass. Emotional pull without release."
    },
    {
        "emotion": "Tenderness",
        "tonal_center": "C major or F major",
        "chord_colors": ["maj7", "6", "add9", "IV → I"],
        "notes_for_generation": "Warm major chords, gentle voice leading, high-register pads or pianos, subtle harmonic motion."
    },
    {
        "emotion": "Shame",
        "tonal_center": "A minor or C Phrygian",
        "chord_colors": ["minor6", "dim", "chromatic bass movement"],
        "notes_for_generation": "Closed voicings, descending basslines, muted dynamics. Harmonic weight that feels constricted or internal."
    },
    {
        "emotion": "Triumph",
        "tonal_center": "D major or A Mixolydian",
        "chord_colors": ["sus2", "IV → I", "maj7", "add9"],
        "notes_for_generation": "Strong major motion with lift. Wide voicings, delayed cadences for emotional payoff."
    },
    {
        "emotion": "Ambivalence",
        "tonal_center": "E♭ major ↔ C minor",
        "chord_colors": ["add9", "maj7", "minor7", "borrowed chords"],
        "notes_for_generation": "Alternate between major and minor qualities. Use modulation or chords that imply two emotional directions."
    },
    {
        "emotion": "Existential Dread",
        "tonal_center": "B Locrian or D minor",
        "chord_colors": ["bII", "dim7", "cluster chords", "drone bass"],
        "notes_for_generation": "Low, dense textures. Sparse harmonic movement. Build unease through dissonant intervals and reverb space."
    },
    {
        "emotion": "Euphoria",
        "tonal_center": "G major or D Lydian",
        "chord_colors": ["maj9", "sus2", "add11", "IV → I"],
        "notes_for_generation": "Bright, open chords with rhythmic drive. Use sidechained pads, uplifting melodies, harmonic clarity."
    },
    {
        "emotion": "Loneliness",
        "tonal_center": "E minor or G minor",
        "chord_colors": ["minor9", "add9", "bVII", "sparse voicing"],
        "notes_for_generation": "Sparse arrangement, wide stereo image, focus on high mids. Echoing delay, unresolved movement."
    },
    {
        "emotion": "Vindication",
        "tonal_center": "B♭ major or D Mixolydian",
        "chord_colors": ["maj7", "add9", "IV → I"],
        "notes_for_generation": "Triumphant but restrained. Major voicings with subtle tension, rhythmic confidence."
    },
    {
        "emotion": "Wonder",
        "tonal_center": "C Lydian or A major",
        "chord_colors": ["maj7", "add9", "#11", "pedal drones"],
        "notes_for_generation": "Floating chords, lush upper extensions, delayed resolutions, sparkle through high-register synths."
    },
    {
        "emotion": "Frustration",
        "tonal_center": "G minor or F Phrygian",
        "chord_colors": ["bII", "sus4", "dim", "minor7b5"],
        "notes_for_generation": "Repeated unresolved motifs. Build-up of harmonic tension that never quite releases."
    },
    {
        "emotion": "Disgust",
        "tonal_center": "C Locrian or D♭ minor",
        "chord_colors": ["bII", "tritone intervals", "dissonant clusters"],
        "notes_for_generation": "Unstable intervals, aggressive harmonics, bitcrushed or detuned chords. Ugly-beautiful tension."
    }
]

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

def chord_name_to_midi_notes(chord_name, root_note=60):
    """
    Convert a chord name like 'Cmaj7' or 'Am add9' to MIDI note numbers.
    Returns a list of MIDI note numbers.
    """
    # Basic chord note mappings (intervals from root)
    chord_patterns = {
        'major': [0, 4, 7],
        'minor': [0, 3, 7],
        'maj7': [0, 4, 7, 11],
        'minor7': [0, 3, 7, 10],
        'm7': [0, 3, 7, 10],
        'add9': [0, 4, 7, 14],  # root, major 3rd, 5th, 9th (octave + 2)
        'sus2': [0, 2, 7],
        'sus4': [0, 5, 7],
        'dim': [0, 3, 6],
        'dim7': [0, 3, 6, 9],
        'maj9': [0, 4, 7, 11, 14],
        'minor9': [0, 3, 7, 10, 14],
        'm9': [0, 3, 7, 10, 14],
        'add11': [0, 4, 7, 17],
        '6': [0, 4, 7, 9],
        'minor6': [0, 3, 7, 9],
        'm6': [0, 3, 7, 9],
        'power': [0, 7],  # power chord (root and 5th)
    }

    # Default to major triad if pattern not found
    return [root_note + interval for interval in chord_patterns.get(chord_name.lower(), [0, 4, 7])]

def parse_chord_progression(progression_text):
    """
    Parse AI-generated chord progression text into a list of chord dictionaries.
    Expected format: "Cmaj7 - Am - Fmaj7 - G"
    Returns: [{'name': 'Cmaj7', 'root': 60, 'notes': [60, 64, 67, 71]}, ...]
    """
    # Note name to MIDI number mapping (C4 = 60)
    note_map = {
        'C': 60, 'C#': 61, 'Db': 61, 'D': 62, 'D#': 63, 'Eb': 63,
        'E': 64, 'F': 65, 'F#': 66, 'Gb': 66, 'G': 67, 'G#': 68,
        'Ab': 68, 'A': 69, 'A#': 70, 'Bb': 70, 'B': 71
    }

    chords = []
    # Split by common delimiters
    chord_names = [c.strip() for c in progression_text.replace('→', '-').split('-')]

    for chord_name in chord_names:
        if not chord_name:
            continue

        # Extract root note
        root_name = chord_name[0].upper()
        if len(chord_name) > 1 and chord_name[1] in ['#', 'b', '♭', '♯']:
            root_name += 'b' if chord_name[1] in ['b', '♭'] else '#'
            quality = chord_name[2:].strip()
        else:
            quality = chord_name[1:].strip()

        root_midi = note_map.get(root_name, 60)
        notes = chord_name_to_midi_notes(quality if quality else 'major', root_midi)

        chords.append({
            'name': chord_name,
            'root': root_midi,
            'notes': notes
        })

    return chords

def create_midi_file(chord_progression, tempo=80, duration_per_chord=4.0):
    """
    Create a MIDI file from a chord progression.
    Returns the MIDI file as bytes.
    """
    # Create MIDI file with 1 track
    midi = MIDIFile(1)
    track = 0
    channel = 0
    time = 0  # Start at beat 0
    volume = 100

    # Add track name and tempo
    midi.addTrackName(track, time, "Chord Progression")
    midi.addTempo(track, time, tempo)

    # Add each chord
    for chord in chord_progression:
        for note in chord['notes']:
            midi.addNote(track, channel, note, time, duration_per_chord, volume)
        time += duration_per_chord

    # Write to bytes buffer
    buffer = io.BytesIO()
    midi.writeFile(buffer)
    buffer.seek(0)
    return buffer.read()

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

    # Create genre blending language based on number of genres
    if len(genres) == 1:
        genre_string = genres[0]
        blend_instruction = f"focusing on {genre_string}"
    else:
        genre_string = " and ".join(genres)
        blend_instruction = f"that FUSES {' and '.join(genres)} together into a single cohesive approach"
    
    exercise_types = [
        {
            "name": "Idea Generation Drill",
            "prompt": f"""Create an idea generation exercise {blend_instruction}.

{"IMPORTANT: The exercise must deeply integrate conventions, tropes, and techniques from BOTH " + " AND ".join(genres) + ". Do not treat them separately - show how they create something NEW together." if len(genres) > 1 else "Focus on core " + genres[0] + " techniques."}

Format:
**Exercise Name**: [Creative name that reflects the genre blend]
**Goal**: [One sentence - what skill this develops]
**Exercise**: [Clear instructions explaining the drill{" - must show how " + " and ".join(genres) + " elements work together" if len(genres) > 1 else ""}]
**Example Progression**: [Show 3 examples from simple to unusual{", each demonstrating the genre fusion" if len(genres) > 1 else ""}]
**Pro Tip**: [One sentence advice about {genre_string}]

At the end, add a section:
**Writing Tips for This Exercise**:
- [Tip 1 specific to this exercise]
- [Tip 2 specific to this exercise]
- [Tip 3 specific to this exercise]

NO character names. Focus on the TECHNIQUE of generating ideas."""
        },
        {
            "name": "World-Building Technique",
            "prompt": f"""Create a world-building exercise {blend_instruction}.

{"CRITICAL: Your world must blend " + " WITH ".join(genres) + " conventions seamlessly. Show how these genres intersect in the world's rules, atmosphere, and logic. The world should feel like a TRUE FUSION, not one genre with the other sprinkled on top." if len(genres) > 1 else ""}

Format:
**Technique Name**: [Name reflecting the {genre_string} blend]
**Goal**: [What this teaches about {genre_string} world-building]
**Exercise**: [Instructions for the technique, 200-250 words{" - explain how to merge " + " and ".join(genres) + " world-building elements into ONE coherent world" if len(genres) > 1 else ""}]
**Rules**:
- [What to do{" - must include both genre elements working together" if len(genres) > 1 else ""}]
- [What to avoid]
**Example Approach**: [2-3 sentences showing the METHOD{" of blending these genres" if len(genres) > 1 else ""}]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 specific to world-building in this genre blend]
- [Tip 2 specific to world-building in this genre blend]
- [Tip 3 specific to world-building in this genre blend]

NO character names. Teach the CRAFT."""
        },
        {
            "name": "Structural Exercise",
            "prompt": f"""Create a structural writing exercise {blend_instruction}.

{"ESSENTIAL: The structure must leverage conventions from BOTH " + " AND ".join(genres) + ". Show how combining these genre structures creates something unique - for example, how " + genres[0] + " pacing might interact with " + genres[1] + " plot architecture." if len(genres) > 1 else ""}

Format:
**Structure Technique**: [Name]
**Goal**: [What this teaches about {genre_string} story structure]
**The Exercise**: [Explain the structural technique{" that combines " + " with ".join(genres) if len(genres) > 1 else ""}]
**Rules**: [Structural constraints that enforce the {genre_string} blend]
**Application**: [How to apply in 500 words]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about {genre_string} story structure]
- [Tip 2 about {genre_string} story structure]
- [Tip 3 about {genre_string} story structure]

Focus on STRUCTURE and TECHNIQUE."""
        },
        {
            "name": "Description Technique",
            "prompt": f"""Create a descriptive writing exercise {blend_instruction}.

{"IMPORTANT: Your descriptive technique must show how to write scenes/settings that feel simultaneously like " + " AND ".join(genres) + ". The atmosphere, sensory details, and word choice should reflect BOTH genres at once." if len(genres) > 1 else ""}

Format:
**Description Technique**: [Name]
**Goal**: [What skill this builds in {genre_string} writing]
**The Challenge**: [Explain the descriptive technique{" for fusing these genres" if len(genres) > 1 else ""}]
**Requirements**:
- [Technical requirement 1{" - must incorporate both genre styles" if len(genres) > 1 else ""}]
- [Technical requirement 2]
- [Word count: 300-400 words]
**Forbidden**: [Generic words/habits to avoid in {genre_string}]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about descriptive writing in this genre blend]
- [Tip 2 about descriptive writing in this genre blend]
- [Tip 3 about descriptive writing in this genre blend]

Teach CRAFT of description."""
        },
        {
            "name": "Dialogue Craft",
            "prompt": f"""Create a dialogue craft exercise {blend_instruction}.

{"KEY: Dialogue should reflect the unique tone created when " + " MEETS ".join(genres) + ". Not alternating between styles, but truly merged - characters speak in a way that embodies BOTH genres." if len(genres) > 1 else ""}

Format:
**Dialogue Technique**: [Name]
**Goal**: [What this teaches about dialogue in {genre_string}]
**The Exercise**: [Instructions on HOW to write dialogue{" that embodies both genres simultaneously" if len(genres) > 1 else ""}]
**What Dialogue Should Reveal**: [3 elements specific to {genre_string}]
**Technical Rules**: [2 dialogue rules for this genre blend]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about dialogue craft in {genre_string}]
- [Tip 2 about dialogue craft in {genre_string}]
- [Tip 3 about dialogue craft in {genre_string}]

Focus on dialogue CRAFT."""
        },
        {
            "name": "Theme & Subtext",
            "prompt": f"""Create a theme/subtext exercise {blend_instruction}.

{"CRITICAL: Explore themes that arise specifically from combining " + " WITH ".join(genres) + ". What unique thematic territory does this mashup unlock? What can you explore by fusing these genres that neither could do alone?" if len(genres) > 1 else ""}

Format:
**Exercise Name**: [Name]
**Goal**: [What this teaches about theme in {genre_string}]
**The Challenge**: [How to embed theme without preaching{" while honoring both genre conventions" if len(genres) > 1 else ""}]
**Approach**: [2-3 techniques for showing theme in this genre blend]
**Practice**: [How to practice this skill in 300-500 words]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about theme and subtext in {genre_string}]
- [Tip 2 about theme and subtext in {genre_string}]
- [Tip 3 about theme and subtext in {genre_string}]

Teach TECHNIQUE of thematic writing."""
        },
        {
            "name": "Genre Fusion Study",
            "prompt": f"""Create a genre fusion exercise {blend_instruction}.

{"MANDATORY: Analyze existing works that successfully blend " + " AND ".join(genres) + ". Identify specific techniques authors use to merge these genres seamlessly. What makes the fusion work?" if len(genres) > 1 else "Analyze core " + genres[0] + " conventions."}

Format:
**Genre Exercise**: [Name]
**Goal**: [What this teaches about {genre_string} craft]
**The Exercise**: [Instructions for understanding and applying the {genre_string} {"fusion" if len(genres) > 1 else "conventions"}]
{"**The Fusion Point**: [Identify exactly where and how " + " and ".join(genres) + " intersect - what makes them compatible?]" if len(genres) > 1 else "**Core Conventions**: [Key " + genres[0] + " elements to master]"}
**What You'll Learn**: [2 skills specific to this genre combination]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about {genre_string} conventions]
- [Tip 2 about {genre_string} conventions]
- [Tip 3 about {genre_string} conventions]

Focus on GENRE FUSION as craft tool."""
        },
        {
            "name": "Reverse Engineering",
            "prompt": f"""Create a reverse engineering exercise {blend_instruction}.

{"IMPORTANT: Choose a work that successfully blends " + " AND ".join(genres) + ". Analyze HOW it integrates both genres seamlessly - what structural, stylistic, and thematic choices create the fusion?" if len(genres) > 1 else ""}

Format:
**Analysis Exercise**: [Name]
**Goal**: [What this teaches about {genre_string} story construction]
**The Exercise**: Pick a {genre_string} story that {("successfully fuses " + " with ".join(genres)) if len(genres) > 1 else "exemplifies the genre"}. Analyze:
- [Element 1 to outline{" - focus on how genres integrate" if len(genres) > 1 else ""}]
- [Element 2 to outline]
- [Element 3 to outline]
- [Element 4 to outline]
**Then**: [What to do with this analysis]
**What You'll Learn**: [The technique this reveals about {genre_string}]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about analyzing {genre_string} stories]
- [Tip 2 about analyzing {genre_string} stories]
- [Tip 3 about analyzing {genre_string} stories]

Teach ANALYTICAL skills."""
        },
        {
            "name": "Constraint Creativity",
            "prompt": f"""Create a constraint-based exercise {blend_instruction}.

{"KEY CONSTRAINT: You must honor conventions from BOTH " + " AND ".join(genres) + " simultaneously. The constraint should force you to find creative ways to integrate them, not just juggle them." if len(genres) > 1 else ""}

Format:
**Constraint Exercise**: [Name]
**Goal**: [What this constraint teaches about {genre_string}]
**The Constraint**: [Specific limitation that forces {genre_string} {"integration - make it impossible to write one genre without the other" if len(genres) > 1 else "mastery"}]
**How to Apply It**: [Instructions for using this constraint in 500-750 words{" - must address both genres simultaneously" if len(genres) > 1 else ""}]
**What This Teaches**: [The craft skill forced by this constraint in {genre_string}]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about working with constraints in {genre_string}]
- [Tip 2 about working with constraints in {genre_string}]
- [Tip 3 about working with constraints in {genre_string}]

Focus on constraints as LEARNING TOOLS."""
        },
        {
            "name": "Revision Technique",
            "prompt": f"""Create a revision exercise {blend_instruction}.

{"FOCUS: Revise specifically for genre integration. Look for places where " + " and ".join(genres) + " feel separate rather than fused. Strengthen the moments where both genres work together." if len(genres) > 1 else ""}

Format:
**Revision Technique**: [Name]
**Goal**: [What editing skill this builds for {genre_string}]
**The Exercise**: Take any draft and apply this technique:
[Specific revision approach step-by-step{" - focus on strengthening the genre blend" if len(genres) > 1 else ""}]
**What to Look For**: [3 red flags in {genre_string} writing]
**The Fix**: [How to revise each issue]

At the end, add:
**Writing Tips for This Exercise**:
- [Tip 1 about revision in {genre_string}]
- [Tip 2 about revision in {genre_string}]
- [Tip 3 about revision in {genre_string}]

Teach REVISION as craft skill."""
        }
    ]
    
    exercise_type = random.choice(exercise_types)
    
    try:
        # Create system message based on whether multiple genres are being blended
        if len(genres) > 1:
            system_message = f"""You are a creative writing instructor specializing in GENRE FUSION. When given multiple genres, you must create exercises that deeply integrate them - not treat them separately or alternate between them.

CRITICAL: If asked to blend {' and '.join(genres)}, the exercise must show how these genres create something NEW together. The fusion should feel inevitable and cohesive, not forced or superficial.

Create exercises that are instructional and teach craft, not story prompts. Avoid character names and specific scenarios. Focus on teaching HOW to write genre-blended work. Always include 3 specific writing tips tailored to the exercise and the genre blend."""
        else:
            system_message = "You are a creative writing instructor teaching techniques and skills. Create exercises that are instructional and teach craft, not story prompts. Avoid character names and specific scenarios. Focus on teaching HOW to write. Always include 3 specific writing tips tailored to the exercise."

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
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
            # Get next book from rotation to ensure even distribution (randomized, no repeats)
            try:
                # Get the shuffled book order and current position from Redis
                book_key = 'sound_design:book_rotation'
                shuffled_key = f'{book_key}:shuffled'
                position_key = f'{book_key}:position'

                # Get current shuffled order
                shuffled_indices = redis_client.get(shuffled_key)

                if shuffled_indices is None:
                    # First time - create a shuffled list of indices
                    indices = list(range(len(all_books)))
                    random.shuffle(indices)
                    redis_client.set(shuffled_key, json.dumps(indices))
                    redis_client.set(position_key, 0)
                    shuffled_indices = indices
                    current_position = 0
                    logger.info(f"[BOOK DEBUG] Created new shuffled book order")
                else:
                    # Parse the shuffled order from JSON
                    shuffled_indices = json.loads(shuffled_indices)
                    current_position = int(redis_client.get(position_key) or 0)

                    # If we've gone through all books, reshuffle for next cycle
                    if current_position >= len(shuffled_indices):
                        indices = list(range(len(all_books)))
                        random.shuffle(indices)
                        redis_client.set(shuffled_key, json.dumps(indices))
                        redis_client.set(position_key, 0)
                        shuffled_indices = indices
                        current_position = 0
                        logger.info(f"[BOOK DEBUG] Reshuffled book order")

                logger.info(f"[BOOK DEBUG] Current position in shuffled list: {current_position}")

                # Get the book at the current shuffled position
                book_index = shuffled_indices[current_position]
                selected_book = all_books[book_index]
                logger.info(f"[BOOK DEBUG] Selected book: {selected_book} (index {book_index})")

                # Increment position for next time
                redis_client.set(position_key, current_position + 1)

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

def generate_drawing_exercise(selected_skills):
    """Generate a drawing exercise based on 1-2 selected skills"""
    import random

    # Skills with their detailed descriptions
    SKILL_INFO = {
        'Observation': {
            'description': 'The ability to actually see what\'s in front of you, not what you think is there',
            'focus': ['seeing angles and proportions accurately', 'noticing subtle shapes', 'recognizing light/shadow patterns', 'comparing distances and negative space']
        },
        'Proportion & Scale': {
            'description': 'Understanding the size relationships between elements',
            'focus': ['measuring relative sizes', 'comparative lengths', 'scale consistency', 'spatial relationships']
        },
        'Gesture': {
            'description': 'Capturing the movement, flow, and energy of a pose',
            'focus': ['body rhythm', 'weight distribution', 'pose essence', 'dynamic flow']
        },
        'Form (3D Thinking)': {
            'description': 'Turning 2D shapes into 3D objects',
            'focus': ['visualizing volumes', 'constructing from simple shapes', 'understanding form in space', 'dimensional thinking']
        },
        'Light & Shadow': {
            'description': 'Understanding how light interacts with form',
            'focus': ['cast shadows', 'core shadows', 'highlights', 'light direction', 'value relationships']
        },
        'Line Control & Mark-Making': {
            'description': 'The physical skill of drawing confident, varied lines',
            'focus': ['line weight variation', 'confident strokes', 'clean contours', 'hatching techniques', 'mark variety']
        },
        'Composition': {
            'description': 'Arranging elements for maximum visual impact',
            'focus': ['balance', 'focal points', 'depth', 'leading lines', 'visual hierarchy']
        }
    }

    # Time durations and difficulty mappings
    difficulty_time_map = {
        'Beginner': '20 minutes',
        'Intermediate': '10 minutes',
        'Advanced': '1 minute'
    }
    difficulties = ['Beginner', 'Intermediate', 'Advanced']

    # Subject matter options
    subjects = [
        'figure drawing', 'still life', 'landscape', 'architecture',
        'hands', 'feet', 'faces', 'drapery', 'animals', 'vehicles',
        'plants', 'interiors', 'portraits', 'urban sketching'
    ]

    skill_string = ' and '.join(selected_skills)
    skill_focus_points = []
    for skill in selected_skills:
        skill_focus_points.extend(SKILL_INFO[skill]['focus'])

    # Create skill-specific exercise prompt based on combinations
    if USE_AI:
        # Build comprehensive prompt for AI
        system_prompt = f"""You are an expert drawing instructor who creates targeted skill-building exercises.

Create a drawing exercise focusing on: {skill_string}

{"CRITICAL: This exercise must integrate BOTH " + " AND ".join(selected_skills) + ". Design the exercise so practicing it naturally develops both skills simultaneously." if len(selected_skills) > 1 else "Focus entirely on developing " + selected_skills[0] + "."}

For context:
{chr(10).join([f"- {skill}: {SKILL_INFO[skill]['description']}" for skill in selected_skills])}

Key focus areas to address:
{chr(10).join([f"- {point}" for point in skill_focus_points[:4]])}

IMPORTANT FORMAT:
1. Start with "Exercise:" followed by a clear, specific exercise title
2. Provide detailed instructions (150-200 words) explaining:
   - What to draw
   - How to approach it
   - What to focus on specifically for the {skill_string} skill(s)
   - Common mistakes to avoid
3. Include a "Success Criteria" section: 3 specific things to check
4. End with 3 practical tips for this specific exercise

Be specific and actionable. Focus on the METHOD, not just the outcome."""

        user_prompt = f"Create a {'skill-fusion' if len(selected_skills) > 1 else skill_string} drawing exercise"

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=600
            )

            content = response.choices[0].message.content.strip()

            # Extract title
            title = f"{skill_string} Exercise"
            lines = content.split('\n')
            for line in lines[:3]:
                if line.startswith('Exercise:'):
                    title = line.replace('Exercise:', '').strip()
                    break

            # Randomly assign difficulty and get corresponding time
            difficulty = random.choice(difficulties)
            estimated_time = difficulty_time_map[difficulty]

            # Extract tips
            tips = []
            in_tips_section = False
            for line in content.split('\n'):
                if 'tip' in line.lower() or 'remember' in line.lower():
                    in_tips_section = True
                if in_tips_section and (line.strip().startswith('-') or line.strip().startswith('•')):
                    tip = line.strip().lstrip('-•').strip()
                    if len(tip) > 10:
                        tips.append(tip)

            if not tips:
                tips = [
                    f"Focus on {skill_focus_points[0]} throughout the exercise",
                    "Don't rush - quality of observation matters more than speed",
                    f"Review your work specifically for {skill_string} development"
                ]

            return {
                'title': title,
                'content': content,
                'skills': selected_skills,
                'difficulty': difficulty,
                'estimatedTime': estimated_time,
                'tips': tips[:3],
                'timestamp': datetime.utcnow().isoformat(),
                'ai_generated': True
            }

        except Exception as e:
            logger.error(f"AI drawing exercise generation failed: {str(e)}")
            # Fall through to template fallback

    # Template fallback
    templates = [
        {
            'type': 'Timed Practice',
            'content': f"""**Exercise:** {skill_string} - Rapid Studies

Set a timer and create multiple quick studies focusing specifically on {skill_string}.

**Instructions:**
Complete 10-15 rapid sketches, each focusing on {', '.join([SKILL_INFO[skill]['focus'][0] for skill in selected_skills])}. {'Work to integrate both skills in each drawing - observe how they inform each other.' if len(selected_skills) > 1 else 'Focus exclusively on this single skill aspect.'}

Start simple and gradually increase complexity. Don't erase - commit to each mark. The goal is building muscle memory and training your eye, not creating finished pieces.

**Success Criteria:**
- You can identify clear improvement from first to last sketch
- {'Both skills are visible in your approach' if len(selected_skills) > 1 else 'The target skill is consistently applied'}
- You're seeing more accurately by the end of the session

**Subject Matter:** Choose from {', '.join(random.sample(subjects, 3))}
**Recommended Time Per Study:** {random.choice(['30 seconds', '1 minute', '2 minutes'])}"""
        },
        {
            'type': 'Focused Study',
            'content': f"""**Exercise:** {skill_string} - Analytical Drawing

Create a single, carefully observed drawing emphasizing {skill_string}.

**Instructions:**
Choose your subject thoughtfully. Before drawing, spend time purely observing and identifying {', '.join([point for skill in selected_skills for point in SKILL_INFO[skill]['focus'][:2]])}.

Draw slowly and methodically. {'Consciously apply both ' + ' and '.join(selected_skills) + ' throughout - notice how they support each other.' if len(selected_skills) > 1 else 'Every mark should demonstrate ' + selected_skills[0] + ' awareness.'}

Take breaks to step back and assess. Compare your drawing to the subject specifically for {skill_string} accuracy.

**Success Criteria:**
- Clear evidence of {skill_string} understanding in the final drawing
- Conscious decision-making visible in your marks
- Accurate representation of the targeted skill elements

**Subject Matter:** {random.choice(subjects)}
**Recommended Approach:** Work from large shapes to small details"""
        },
        {
            'type': 'Blind Contour Variation',
            'content': f"""**Exercise:** {skill_string} - Observation Through Restriction

Use blind/modified blind contour drawing to isolate and develop {skill_string}.

**Instructions:**
Draw your subject while looking {'95% at the subject, 5% at your paper' if random.random() > 0.5 else 'only at the subject (true blind contour)'}. Focus intensely on {', '.join([SKILL_INFO[skill]['focus'][0] for skill in selected_skills])}.

{'This exercise forces both ' + ' and '.join(selected_skills) + " to work together since you can't rely on correction." if len(selected_skills) > 1 else 'This restriction forces pure ' + selected_skills[0] + " without the ability to correct."}

The goal isn't a "good" drawing - it's training your eye-hand connection and observation skills.

**Success Criteria:**
- You maintained focus on the subject, not your paper
- The drawing shows understanding of {skill_string} even if distorted
- You can identify what you learned about seeing

**Subject Matter:** {random.choice(['your non-dominant hand', 'a plant', 'a shoe', 'a chair', 'your face in a mirror'])}
**Duration:** {random.choice(['5 minutes', '10 minutes', '15 minutes'])}"""
        }
    ]

    template = random.choice(templates)
    difficulty = random.choice(difficulties)
    estimated_time = difficulty_time_map[difficulty]

    tips = [
        f"The exercise specifically targets {skill_string} - stay focused on these aspects",
        f"{'Notice how ' + ' and '.join(selected_skills) + ' inform each other as you work' if len(selected_skills) > 1 else 'Every decision should reinforce ' + selected_skills[0]}",
        "Repetition builds skill - consider doing this exercise multiple times this week"
    ]

    return {
        'title': f"{skill_string} - {template['type']}",
        'content': template['content'],
        'skills': selected_skills,
        'difficulty': difficulty,
        'estimatedTime': estimated_time,
        'tips': tips,
        'timestamp': datetime.utcnow().isoformat(),
        'ai_generated': False
    }

def generate_chord_progression(selected_emotions):
    """Generate a chord progression based on 1-2 selected emotions"""
    # Get emotion data
    emotion_data = [e for e in EMOTIONS if e['emotion'] in selected_emotions]

    if not emotion_data:
        raise ValueError("No valid emotions selected")

    # Combine emotion notes for AI prompt
    combined_notes = " ".join([e['notes_for_generation'] for e in emotion_data])
    combined_tonal_centers = ", ".join([e['tonal_center'] for e in emotion_data])
    combined_chord_colors = list(set([color for e in emotion_data for color in e['chord_colors']]))
    emotion_names = " + ".join([e['emotion'] for e in emotion_data])

    # Generate with AI if available
    if USE_AI:
        system_prompt = f"""You are a music theory expert and composer specializing in emotional harmonic progression.

Create a chord progression that evokes: {emotion_names}

Tonal Center(s): {combined_tonal_centers}
Suggested Chord Colors: {', '.join(combined_chord_colors)}

Guidelines:
{combined_notes}

IMPORTANT FORMAT:
1. Start with "Progression:" followed by the chord progression (e.g., "Progression: Cmaj7 - Am7 - Fmaj7 - G")
2. Then provide a detailed explanation of WHY this progression was created, including:
   - How the harmonic choices reflect the emotion(s)
   - Voice leading and tension/resolution decisions
   - The emotional arc of the progression
   - Specific intervals or movements that create the feeling

Keep the progression 4-8 chords. Be specific about chord qualities (maj7, add9, sus2, etc)."""

        user_prompt = f"Create a chord progression for: {emotion_names}"

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()

            # Parse the response to extract progression and explanation
            lines = content.split('\n')
            progression_line = ""
            explanation = []

            for i, line in enumerate(lines):
                if line.startswith("Progression:"):
                    progression_line = line.replace("Progression:", "").strip()
                elif progression_line:  # After we found the progression, rest is explanation
                    explanation.append(line)

            if not progression_line:
                # Try to find chord progression in first line
                progression_line = lines[0].strip()
                explanation = lines[1:]

            explanation_text = "\n".join(explanation).strip()

            # Parse chord progression
            chords = parse_chord_progression(progression_line)

            # Create MIDI file
            midi_bytes = create_midi_file(chords, tempo=80, duration_per_chord=4.0)
            midi_base64 = base64.b64encode(midi_bytes).decode('utf-8')

            # Determine difficulty and time based on complexity
            num_chords = len(chords)
            if num_chords <= 4:
                difficulty = "Beginner"
                estimated_time = "10 minutes"
            elif num_chords <= 6:
                difficulty = "Intermediate"
                estimated_time = "15 minutes"
            else:
                difficulty = "Advanced"
                estimated_time = "20 minutes"

            return {
                'title': f"{emotion_names} Chord Progression",
                'progression': progression_line,
                'explanation': explanation_text,
                'emotions': selected_emotions,
                'difficulty': difficulty,
                'estimatedTime': estimated_time,
                'midiFile': midi_base64
            }

        except Exception as e:
            logger.error(f"Chord progression AI generation failed: {str(e)}")
            # Fall through to template-based generation

    # Template-based fallback
    # Simple progression based on first emotion
    emotion = emotion_data[0]
    tonal_center = emotion['tonal_center'].split(' or ')[0]  # Pick first option

    # Extract key from tonal center
    if 'minor' in tonal_center:
        key_note = tonal_center.split(' ')[0]
        progression = f"{key_note}m - {key_note}m7 - {key_note}m add9 - {key_note}m"
    else:
        key_note = tonal_center.split(' ')[0]
        progression = f"{key_note} - {key_note}maj7 - {key_note} add9 - {key_note}"

    chords = parse_chord_progression(progression)
    midi_bytes = create_midi_file(chords)
    midi_base64 = base64.b64encode(midi_bytes).decode('utf-8')

    return {
        'title': f"{emotion_names} Chord Progression",
        'progression': progression,
        'explanation': f"A simple {tonal_center} progression designed to evoke {emotion_names.lower()}. {emotion['notes_for_generation']}",
        'emotions': selected_emotions,
        'difficulty': "Beginner",
        'estimatedTime': "10 minutes",
        'midiFile': midi_base64
    }

@app.route('/generate-chord-progression', methods=['POST'])
def generate_chord_progression_endpoint():
    """Generate a chord progression based on selected emotions"""
    with tracer.start_as_current_span("generate-chord-progression") as span:
        try:
            data = request.json
            emotions = data.get('emotions', [])
            user_id = data.get('userId', 'anonymous')

            span.set_attribute("user.id", user_id)
            span.set_attribute("emotions", str(emotions))

            # Validate inputs
            if not emotions or len(emotions) < 1 or len(emotions) > 2:
                return jsonify({'error': 'Must select 1 or 2 emotions'}), 400

            valid_emotions = [e['emotion'] for e in EMOTIONS]
            for emotion in emotions:
                if emotion not in valid_emotions:
                    return jsonify({'error': f'Invalid emotion: {emotion}'}), 400

            # Generate progression
            span.add_event("generating-chord-progression")
            result = generate_chord_progression(emotions)

            # Track metrics
            span.set_attribute("progression.title", result['title'])
            span.set_attribute("progression.difficulty", result['difficulty'])

            return jsonify(result), 200

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Chord progression generation failed: {str(e)}")
            return jsonify({'error': 'Failed to generate chord progression'}), 500

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

@app.route('/generate-drawing-exercise', methods=['POST'])
def generate_drawing_exercise_endpoint():
    """Generate a drawing exercise based on selected skills"""
    with tracer.start_as_current_span("generate-drawing-exercise") as span:
        try:
            data = request.json
            skills = data.get('skills', [])
            user_id = data.get('userId', 'anonymous')

            span.set_attribute("user.id", user_id)
            span.set_attribute("skills", str(skills))

            # Validate inputs
            if not skills or len(skills) < 1 or len(skills) > 2:
                return jsonify({'error': 'Must select 1 or 2 skills'}), 400

            valid_skills = [
                'Observation', 'Proportion & Scale', 'Gesture',
                'Form (3D Thinking)', 'Light & Shadow',
                'Line Control & Mark-Making', 'Composition'
            ]
            for skill in skills:
                if skill not in valid_skills:
                    return jsonify({'error': f'Invalid skill: {skill}'}), 400

            # Generate exercise
            span.add_event("generating-drawing-exercise")
            result = generate_drawing_exercise(skills)

            # Track metrics
            span.set_attribute("exercise.title", result['title'])
            span.set_attribute("exercise.difficulty", result['difficulty'])
            span.set_attribute("exercise.estimated_time", result['estimatedTime'])

            return jsonify(result), 200

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Drawing exercise generation failed: {str(e)}")
            return jsonify({'error': 'Failed to generate drawing exercise'}), 500

@app.route('/generate-writing-feedback', methods=['POST'])
def generate_writing_feedback_endpoint():
    """Generate AI feedback for a writing exercise submission"""
    with tracer.start_as_current_span("generate-writing-feedback") as span:
        try:
            data = request.json
            exercise = data.get('exercise', '')
            exercise_type = data.get('exerciseType', '')
            user_writing = data.get('userWriting', '')
            genres = data.get('genres', [])
            difficulty = data.get('difficulty', '')
            word_count = data.get('wordCount', 0)

            span.set_attribute("exercise.type", exercise_type)
            span.set_attribute("genres", str(genres))
            span.set_attribute("difficulty", difficulty)
            span.set_attribute("wordCount.target", word_count)
            span.set_attribute("wordCount.actual", len(user_writing.split()))

            # Validate inputs
            if not user_writing or not exercise:
                return jsonify({'error': 'Missing required fields'}), 400

            # Generate feedback using AI
            if USE_AI:
                try:
                    span.add_event("generating-ai-feedback")

                    system_prompt = f"""You are an experienced creative writing instructor providing direct, one-on-one feedback. Address the writer as "you" throughout—speak to them directly, as if you're sitting across from them reviewing their work together.

The writer completed this exercise:
{exercise}

Exercise Type: {exercise_type}
Genres: {', '.join(genres)}
Difficulty: {difficulty}
Target Word Count: {word_count} words

Provide critical but encouraging feedback covering:

1. **What Works**: Identify 1-2 genuine strengths in their writing. Be specific—quote or reference exact moments. Don't praise generically or find positives where there aren't any. If the writing is weak overall, note any small bright spots but be honest about the overall level.

2. **Critical Issues**: Identify the 2-3 most significant problems holding this piece back. Be direct and specific:
   - What exactly isn't working? (weak verb choices, unclear sentences, cliché descriptions, etc.)
   - Why is it a problem? (undermines tension, confuses the reader, tells instead of shows, etc.)
   - Give concrete examples from their writing

3. **Genre & Exercise Execution**: Did they actually do what was asked? Be honest:
   - Are genre conventions present or just superficially applied?
   - Did they engage with the core challenge of the exercise or avoid it?
   - What did they miss or misunderstand?

4. **Craft Analysis**: Assess the technical writing:
   - Prose clarity and style
   - Sentence variety and rhythm
   - Show vs. tell balance
   - Dialogue authenticity (if applicable)
   - Pacing and structure

   Be specific. Point to patterns. Don't sugarcoat weak craft.

5. **Priority Revisions**: What are the 1-2 most important things for them to fix first? Be direct about what will make the biggest difference.

CRITICAL APPROACH:
- Address the writer as "you" - this is direct feedback to them
- Be honest. If something doesn't work, say so clearly
- Support criticism with specific evidence from their writing
- Recognize effort, but focus on results
- Don't inflate praise—writers grow from truth, not false encouragement
- End with genuine belief in their potential IF they apply the feedback
- Use a mentor's voice: firm, honest, but invested in their growth"""

                    user_prompt = f"Here is my writing for you to review:\n\n{user_writing}"

                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=800
                    )

                    feedback = response.choices[0].message.content.strip()

                    span.set_attribute("feedback.length", len(feedback))
                    return jsonify({'feedback': feedback}), 200

                except Exception as ai_error:
                    logger.error(f"AI feedback generation failed: {str(ai_error)}")
                    # Fall through to template feedback

            # Template fallback feedback
            actual_word_count = len(user_writing.split())
            word_count_feedback = ""
            if actual_word_count >= word_count:
                word_count_feedback = f"Great job meeting the {word_count} word target!"
            else:
                word_count_feedback = f"You wrote {actual_word_count} words. Consider expanding to reach the {word_count} word goal."

            template_feedback = f"""**Feedback on your {exercise_type}**

**Strengths:**
• You completed the writing exercise and engaged with the prompt
• Your work shows effort in addressing the {', '.join(genres)} genre(s)
• {word_count_feedback}

**Areas for Development:**
• Consider deepening your exploration of the genre conventions
• Review the exercise requirements to ensure all aspects are fully addressed
• Focus on refining your prose and strengthening your narrative voice

**Next Steps:**
• Revise with the exercise goals in mind
• Read examples in the {', '.join(genres)} genre(s) to study craft techniques
• Consider sharing your work for peer feedback

Keep writing and developing your craft!"""

            return jsonify({'feedback': template_feedback}), 200

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Writing feedback generation failed: {str(e)}")
            return jsonify({'error': 'Failed to generate writing feedback'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_ENV') == 'development')