import pytest
import json
from unittest.mock import patch, MagicMock

class TestPromptGeneration:
    """Test prompt generation endpoints."""

    def test_generate_prompt_success(self, client, mock_openai_response):
        """Test successful prompt generation."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = mock_openai_response

            response = client.post('/api/generate-prompt',
                                   json={
                                       'genres': ['Fantasy', 'Science Fiction'],
                                       'exerciseType': 'Idea Generation Drills'
                                   })

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'title' in data
            assert 'content' in data
            assert 'difficulty' in data
            assert 'wordCount' in data

    def test_generate_prompt_missing_genres(self, client):
        """Test prompt generation without genres."""
        response = client.post('/api/generate-prompt', json={})

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_generate_prompt_invalid_genre_count(self, client):
        """Test prompt generation with too many genres."""
        response = client.post('/api/generate-prompt',
                               json={'genres': ['Fantasy', 'Sci-Fi', 'Mystery']})

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert '1-2 genres' in data['error'].lower()

    def test_generate_prompt_empty_genres_array(self, client):
        """Test prompt generation with empty genres array."""
        response = client.post('/api/generate-prompt', json={'genres': []})

        assert response.status_code == 400

    def test_generate_prompt_invalid_genres_type(self, client):
        """Test prompt generation with non-array genres."""
        response = client.post('/api/generate-prompt',
                               json={'genres': 'Fantasy'})

        assert response.status_code == 400

    def test_generate_prompt_with_exercise_type(self, client, mock_openai_response):
        """Test prompt generation with specific exercise type."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = mock_openai_response

            response = client.post('/api/generate-prompt',
                                   json={
                                       'genres': ['Fantasy'],
                                       'exerciseType': 'Dialogue Craft'
                                   })

            assert response.status_code == 200
            assert mock_openai.called

            # Verify exercise type is in the prompt
            call_args = mock_openai.call_args
            messages = call_args[1]['messages']
            prompt_text = str(messages)
            assert 'Dialogue Craft' in prompt_text

    def test_generate_prompt_handles_openai_error(self, client):
        """Test handling of OpenAI API errors."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.side_effect = Exception('API Error')

            response = client.post('/api/generate-prompt',
                                   json={'genres': ['Fantasy']})

            # Should return template fallback
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'title' in data

    def test_prompt_includes_tips(self, client, mock_openai_response):
        """Test that generated prompts include tips."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = mock_openai_response

            response = client.post('/api/generate-prompt',
                                   json={'genres': ['Fantasy']})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'tips' in data
            assert isinstance(data['tips'], list)

    def test_difficulty_distribution(self, client, mock_openai_response):
        """Test that difficulty levels are properly assigned."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = mock_openai_response

            difficulties = set()
            word_counts = set()

            # Generate multiple prompts to test distribution
            for _ in range(20):
                response = client.post('/api/generate-prompt',
                                       json={'genres': ['Fantasy']})
                data = json.loads(response.data)
                difficulties.add(data['difficulty'])
                word_counts.add(data['wordCount'])

            # Should have variety in difficulties
            valid_difficulties = {'Very Easy', 'Easy', 'Medium', 'Hard'}
            assert difficulties.issubset(valid_difficulties)

            # Word counts should correspond to difficulties
            valid_word_counts = {250, 500, 750, 1000}
            assert word_counts.issubset(valid_word_counts)


class TestSoundDesignPrompts:
    """Test sound design prompt generation."""

    def test_generate_technical_exercise(self, client, mock_openai_response):
        """Test technical sound design exercise generation."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            with patch('redis.Redis') as mock_redis:
                mock_redis_instance = MagicMock()
                mock_redis.return_value = mock_redis_instance
                mock_redis_instance.get.return_value = None

                mock_openai.return_value = mock_openai_response

                response = client.post('/api/sound-design-prompts',
                                       json={
                                           'synthesizer': 'Serum 2',
                                           'exerciseType': 'technical',
                                           'genre': 'Dubstep'
                                       })

                assert response.status_code == 200
                data = json.loads(response.data)
                assert 'title' in data
                assert 'Serum 2' in data.get('title', '') or 'Serum 2' in data.get('content', '')

    def test_generate_creative_exercise(self, client, mock_openai_response):
        """Test creative sound design exercise generation."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            with patch('redis.Redis') as mock_redis:
                mock_redis_instance = MagicMock()
                mock_redis.return_value = mock_redis_instance
                mock_redis_instance.get.return_value = None

                mock_openai.return_value = mock_openai_response

                response = client.post('/api/sound-design-prompts',
                                       json={
                                           'synthesizer': 'Phase Plant',
                                           'exerciseType': 'creative'
                                       })

                assert response.status_code == 200

    def test_artist_rotation(self, client, mock_openai_response):
        """Test that artists rotate without repetition."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            with patch('redis.Redis') as mock_redis:
                mock_redis_instance = MagicMock()
                mock_redis.return_value = mock_redis_instance

                used_artists = []
                mock_redis_instance.smembers.return_value = set()
                mock_redis_instance.scard.return_value = len(used_artists)

                mock_openai.return_value = mock_openai_response

                response = client.post('/api/sound-design-prompts',
                                       json={
                                           'synthesizer': 'Serum 2',
                                           'exerciseType': 'technical',
                                           'genre': 'Dubstep'
                                       })

                assert response.status_code == 200
                # Verify Redis methods were called for artist rotation
                assert mock_redis_instance.smembers.called or mock_redis_instance.sadd.called


class TestChordProgressionGeneration:
    """Test chord progression generation."""

    def test_generate_chord_progression(self, client, mock_openai_response):
        """Test chord progression generation."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'progression': 'Cmaj7 - Am7 - Fmaj7 - G',
                            'explanation': 'Test explanation',
                            'difficulty': 'Intermediate'
                        })
                    }
                }]
            }

            response = client.post('/api/chord-progression',
                                   json={'emotions': ['Melancholy', 'Longing']})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'progression' in data
            assert 'midiFile' in data

    def test_chord_progression_missing_emotions(self, client):
        """Test chord progression without emotions."""
        response = client.post('/api/chord-progression', json={})

        assert response.status_code == 400

    def test_chord_progression_invalid_emotion_count(self, client):
        """Test chord progression with too many emotions."""
        response = client.post('/api/chord-progression',
                               json={'emotions': ['Happy', 'Sad', 'Angry']})

        assert response.status_code == 400

    def test_midi_file_generation(self, client, mock_openai_response):
        """Test that MIDI file is properly generated."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'progression': 'Cmaj7 - Am7',
                            'explanation': 'Test',
                            'difficulty': 'Beginner'
                        })
                    }
                }]
            }

            response = client.post('/api/chord-progression',
                                   json={'emotions': ['Melancholy']})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'midiFile' in data
            # MIDI file should be base64 encoded
            import base64
            try:
                base64.b64decode(data['midiFile'])
                is_base64 = True
            except:
                is_base64 = False
            assert is_base64


class TestDrawingPrompts:
    """Test drawing exercise generation."""

    def test_generate_drawing_prompt(self, client, mock_openai_response):
        """Test drawing prompt generation."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = mock_openai_response

            response = client.post('/api/drawing-prompts',
                                   json={'skills': ['Gesture', 'Form (3D Thinking)']})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'title' in data
            assert 'content' in data
            assert 'skills' in data
            assert data['skills'] == ['Gesture', 'Form (3D Thinking)']

    def test_drawing_prompt_missing_skills(self, client):
        """Test drawing prompt without skills."""
        response = client.post('/api/drawing-prompts', json={})

        assert response.status_code == 400

    def test_drawing_prompt_invalid_skill_count(self, client):
        """Test drawing prompt with too many skills."""
        response = client.post('/api/drawing-prompts',
                               json={'skills': ['Skill1', 'Skill2', 'Skill3']})

        assert response.status_code == 400

    def test_drawing_prompt_includes_tips(self, client, mock_openai_response):
        """Test that drawing prompts include tips."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = mock_openai_response

            response = client.post('/api/drawing-prompts',
                                   json={'skills': ['Gesture']})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'tips' in data
            assert isinstance(data['tips'], list)
            assert len(data['tips']) == 3  # Should have 3 tips

    def test_drawing_prompt_difficulty_and_time(self, client, mock_openai_response):
        """Test that drawing prompts have appropriate difficulty and time."""
        with patch('openai.ChatCompletion.create') as mock_openai:
            mock_openai.return_value = mock_openai_response

            response = client.post('/api/drawing-prompts',
                                   json={'skills': ['Gesture']})

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'difficulty' in data
            assert data['difficulty'] in ['Beginner', 'Intermediate', 'Advanced']
            assert 'estimatedTime' in data
            assert 'minute' in data['estimatedTime'].lower()
