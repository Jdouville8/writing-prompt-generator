import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { GoogleLogin } from '@react-oauth/google';
import { trace } from '@opentelemetry/api';
import GenreSelector from './components/GenreSelector';
import PromptDisplay from './components/PromptDisplay';
import { loginUser, logoutUser, restoreUser } from './store/authSlice';
import { generatePrompt } from './store/promptSlice';
import './App.css';

const tracer = trace.getTracer('frontend-app');

function App() {
  const dispatch = useDispatch();
  const { user, isAuthenticated } = useSelector((state) => state.auth);
  const { prompt, loading, error } = useSelector((state) => state.prompt);
  const [selectedGenres, setSelectedGenres] = useState([]);

  // Restore user session on mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    const userStr = localStorage.getItem('user');
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        dispatch(restoreUser({ user }));
      } catch (error) {
        console.error('Failed to restore user:', error);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
      }
    }
  }, [dispatch]);

  const genres = [
    'Fantasy', 'Science Fiction', 'Mystery', 'Thriller', 'Romance',
    'Horror', 'Historical Fiction', 'Literary Fiction', 'Young Adult',
    'Crime', 'Adventure', 'Dystopian', 'Magical Realism', 'Western',
    'Biography', 'Self-Help', 'Philosophy', 'Poetry'
  ];

  const handleGoogleSuccess = async (credentialResponse) => {
    const span = tracer.startSpan('google-login');
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/auth/google`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          credential: credentialResponse.credential
        })
      });
      
      const data = await response.json();
      dispatch(loginUser(data));
    } catch (error) {
      console.error('Login failed:', error);
    } finally {
      span.end();
    }
  };

  const handleGeneratePrompt = async () => {
    if (selectedGenres.length === 0) {
      alert('Please select at least one genre');
      return;
    }

    const span = tracer.startSpan('generate-prompt');
    span.setAttributes({
      'genres.count': selectedGenres.length,
      'genres.selected': selectedGenres.join(',')
    });

    try {
      dispatch(generatePrompt(selectedGenres));
    } finally {
      span.end();
    }
  };

  const handleGenreToggle = (genre) => {
    setSelectedGenres(prev => {
      if (prev.includes(genre)) {
        return prev.filter(g => g !== genre);
      }
      return [...prev, genre];
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <h1 className="text-3xl font-bold text-gray-900">
                📚 Writing Prompt Generator
              </h1>
            </div>
            
            <div className="flex items-center space-x-4">
              {!isAuthenticated ? (
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => console.log('Login Failed')}
                  theme="filled_blue"
                  size="large"
                />
              ) : (
                <div className="flex items-center space-x-4">
                  <img
                    className="h-8 w-8 rounded-full"
                    src={user?.picture}
                    alt={user?.name}
                  />
                  <span className="text-gray-700">{user?.name}</span>
                  <button
                    onClick={() => dispatch(logoutUser())}
                    className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-md transition duration-200"
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {!isAuthenticated ? (
          <div className="text-center py-20">
            <h2 className="text-4xl font-bold text-gray-800 mb-4">
              Welcome to Writing Prompt Generator
            </h2>
            <p className="text-xl text-gray-600 mb-8">
              Sign in with Google to start generating creative writing prompts
            </p>
            <div className="flex justify-center">
              <GoogleLogin
                onSuccess={handleGoogleSuccess}
                onError={() => console.log('Login Failed')}
                theme="filled_blue"
                size="large"
                text="continue_with"
              />
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Genre Selection */}
            <div className="bg-white rounded-lg shadow-xl p-8">
              <h2 className="text-2xl font-bold text-gray-800 mb-6">
                Select Your Genres
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {genres.map((genre) => (
                  <button
                    key={genre}
                    onClick={() => handleGenreToggle(genre)}
                    className={`px-4 py-2 rounded-lg font-medium transition-all duration-200 ${
                      selectedGenres.includes(genre)
                        ? 'bg-indigo-600 text-white shadow-md transform scale-105'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {genre}
                  </button>
                ))}
              </div>
            </div>

            {/* Generate Button */}
            <div className="flex justify-center">
              <button
                onClick={handleGeneratePrompt}
                disabled={loading || selectedGenres.length === 0}
                className={`px-8 py-4 rounded-lg font-bold text-lg transition-all duration-200 ${
                  loading || selectedGenres.length === 0
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white hover:from-purple-700 hover:to-indigo-700 shadow-lg transform hover:scale-105'
                }`}
              >
                {loading ? (
                  <span className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Generating...
                  </span>
                ) : (
                  '✨ Generate Writing Prompt'
                )}
              </button>
            </div>

            {/* Prompt Display */}
            {prompt && (
              <PromptDisplay 
                prompt={prompt}
                genres={selectedGenres}
              />
            )}

            {/* Error Display */}
            {error && (
              <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-red-700">
                      {error}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 text-white mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <p className="text-gray-300">
              Built with React, Node.js, Python, and ❤️
            </p>
            <p className="text-gray-400 mt-2 text-sm">
              Powered by AWS, GCP, Azure | Monitored with Prometheus & OpenTelemetry
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;