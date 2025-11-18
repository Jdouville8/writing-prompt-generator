import pytest
import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def app():
    """Create and configure a test instance of the Flask app."""
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    return flask_app

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        'choices': [{
            'message': {
                'content': 'Test prompt content'
            }
        }]
    }

@pytest.fixture
def mock_feedback_response():
    """Mock feedback response."""
    return {
        'choices': [{
            'message': {
                'content': '### Strengths\n\nGood work!\n\n### Areas for Improvement\n\nConsider adding more detail.'
            }
        }]
    }
