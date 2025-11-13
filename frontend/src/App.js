import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { GoogleLogin } from '@react-oauth/google';
import { trace } from '@opentelemetry/api';
import PromptDisplay from './components/PromptDisplay';
import SynthSelector from './components/SynthSelector';
import SoundDesignPromptDisplay from './components/SoundDesignPromptDisplay';
import ChordProgressionPromptDisplay from './components/ChordProgressionPromptDisplay';
import BookBackground from './components/BookBackground';
import { loginUser, logoutUser, restoreUser } from './store/authSlice';
import { generatePrompt } from './store/promptSlice';
import { generateSoundDesignPrompt, setSynthesizer, setExerciseType, setGenre } from './store/soundDesignSlice';
import { useTheme } from './contexts/ThemeContext';
import './App.css';

const tracer = trace.getTracer('frontend-app');

function App() {
  const dispatch = useDispatch();
  const { user, isAuthenticated } = useSelector((state) => state.auth);
  const { prompt, loading, error } = useSelector((state) => state.prompt);
   const {
    prompt: soundDesignPrompt,
    loading: soundDesignLoading,
    error: soundDesignError,
    selectedSynthesizer,
    selectedExerciseType,
    selectedGenre
  } = useSelector((state) => state.soundDesign);
  const [selectedGenres, setSelectedGenres] = useState([]);
  const [activeTab, setActiveTab] = useState('writing'); // 'writing', 'sound-design', or 'chord-progression'
  const { isDarkMode, toggleTheme } = useTheme();

  // Chord Progression states
  const [selectedEmotions, setSelectedEmotions] = useState([]);
  const [chordProgression, setChordProgression] = useState(null);
  const [chordProgressionLoading, setChordProgressionLoading] = useState(false);
  const [chordProgressionError, setChordProgressionError] = useState(null);

  const emotions = [
    'Melancholy', 'Elation', 'Resentment', 'Awe', 'Nostalgia', 'Serenity',
    'Apprehension', 'Defiance', 'Longing', 'Tenderness', 'Shame', 'Triumph',
    'Ambivalence', 'Existential Dread', 'Euphoria', 'Loneliness', 'Vindication',
    'Wonder', 'Frustration', 'Disgust'
  ];

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
      alert('Please select at least 1 genre (max 2)');
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
      } else {
        // Max 2 genres
        if (prev.length >= 2) {
          return [...prev.slice(1), genre];
        }
        return [...prev, genre];
      }
    });
  };

  const handleGenerateSoundDesign = async () => {
    console.log('=== GENERATE BUTTON CLICKED ===');
    console.log('[APP DEBUG] handleGenerateSoundDesign called with state:', {
      selectedSynthesizer,
      selectedExerciseType,
      selectedGenre
    });

    const span = tracer.startSpan('generate-sound-design-prompt');
    span.setAttributes({
      'synthesizer': selectedSynthesizer,
      'exercise.type': selectedExerciseType,
      'genre': selectedGenre
    });

    try {
      dispatch(generateSoundDesignPrompt({
        synthesizer: selectedSynthesizer,
        exerciseType: selectedExerciseType,
        genre: selectedGenre
      }));
    } finally {
      span.end();
    }
  };

  const handleSynthesizerChange = (synth) => {
    dispatch(setSynthesizer(synth));
  };

  const handleExerciseTypeChange = (type) => {
    console.log('Exercise type changed to:', type);
    console.log('Current selectedGenre:', selectedGenre);
    dispatch(setExerciseType(type));
  };

  const handleGenreChange = (genre) => {
    console.log('Genre changed to:', genre);
    dispatch(setGenre(genre));
  };

  // Chord Progression handlers
  const handleEmotionToggle = (emotion) => {
    setSelectedEmotions(prev => {
      if (prev.includes(emotion)) {
        return prev.filter(e => e !== emotion);
      } else {
        // Max 2 emotions
        if (prev.length >= 2) {
          return [...prev.slice(1), emotion];
        }
        return [...prev, emotion];
      }
    });
  };

  const handleGenerateChordProgression = async () => {
    if (selectedEmotions.length === 0) {
      alert('Please select at least 1 emotion (max 2)');
      return;
    }

    const span = tracer.startSpan('generate-chord-progression');
    span.setAttributes({
      'emotions.count': selectedEmotions.length,
      'emotions.selected': selectedEmotions.join(',')
    });

    setChordProgressionLoading(true);
    setChordProgressionError(null);

    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/chord-progression/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          emotions: selectedEmotions,
          userId: user?.id || 'anonymous'
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate chord progression');
      }

      const data = await response.json();
      setChordProgression(data);
    } catch (error) {
      console.error('Chord progression generation failed:', error);
      setChordProgressionError(error.message);
    } finally {
      setChordProgressionLoading(false);
      span.end();
    }
  };

  return (
    <div className={`min-h-screen transition-colors duration-200 ${isDarkMode ? 'bg-gradient-to-br from-gray-900 to-gray-800' : 'bg-gradient-to-br from-purple-50 to-indigo-100'}`}>
      {/* Header */}
      <header className={`shadow-lg transition-colors duration-200 ${isDarkMode ? 'bg-gray-800' : 'bg-white'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <h1 className={`text-3xl font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                Ideasthesia Creative Prompt Generator
              </h1>
            </div>

            <div className="flex items-center space-x-4">
              {/* Dark Mode Toggle */}
              <button
                onClick={toggleTheme}
                className={`p-2 rounded-lg transition-colors duration-200 ${
                  isDarkMode
                    ? 'bg-gray-700 hover:bg-gray-600 text-yellow-400'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
                aria-label="Toggle dark mode"
              >
                {isDarkMode ? (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                )}
              </button>
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
                  <span className={isDarkMode ? 'text-gray-200' : 'text-gray-700'}>{user?.name}</span>
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

      {/* Tab Navigation - Only shown when authenticated */}
      {isAuthenticated && (
        <div className={`border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex space-x-8">
              <button
                onClick={() => setActiveTab('writing')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-200 ${
                  activeTab === 'writing'
                    ? isDarkMode
                      ? 'border-indigo-500 text-indigo-400'
                      : 'border-indigo-600 text-indigo-600'
                    : isDarkMode
                    ? 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                📝 Writing Prompts
              </button>
              <button
                onClick={() => setActiveTab('sound-design')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-200 ${
                  activeTab === 'sound-design'
                    ? isDarkMode
                      ? 'border-purple-500 text-purple-400'
                      : 'border-purple-600 text-purple-600'
                    : isDarkMode
                    ? 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                🎹 Sound Design
              </button>
              <button
                onClick={() => setActiveTab('chord-progression')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors duration-200 ${
                  activeTab === 'chord-progression'
                    ? isDarkMode
                      ? 'border-blue-500 text-blue-400'
                      : 'border-blue-600 text-blue-600'
                    : isDarkMode
                    ? 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                🎼 Chord Progressions
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {!isAuthenticated ? (
          <div className="text-center py-20">
            <h2 className={`text-4xl font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-800'}`}>
              Welcome to Creative Prompt Generator
            </h2>
            <p className={`text-xl mb-8 ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
              Sign in with Google to start generating creative writing prompts and sound design exercises
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
            {/* Writing Prompts Tab */}
            {activeTab === 'writing' && (
              <>
                {/* Genre Selection */}
                <div className={`relative rounded-lg shadow-xl p-8 transition-colors duration-200 ${isDarkMode ? 'bg-gray-800' : 'bg-white'}`}>
                  <BookBackground />
                  <div className="relative z-10">
                    <h2 className={`text-2xl font-bold mb-6 ${isDarkMode ? 'text-white' : 'text-gray-800'}`}>
                      Select Your Genres {selectedGenres.length > 0 && `(${selectedGenres.length}/2)`}
                    </h2>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {genres.map((genre) => (
                  <button
                    key={genre}
                    onClick={() => handleGenreToggle(genre)}
                    className={`px-4 py-2 rounded-lg font-medium transition-all duration-200 ${
                      selectedGenres.includes(genre)
                        ? 'bg-indigo-600 text-white shadow-md transform scale-105'
                        : isDarkMode
                        ? 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {genre}
                  </button>
                ))}
                </div>
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
              </>
            )}

            {/* Sound Design Tab */}
            {activeTab === 'sound-design' && (
              <>
                {/* Synth and Exercise Type Selection */}
                <div className={`rounded-lg shadow-xl p-8 transition-colors duration-200 ${isDarkMode ? 'bg-gray-800' : 'bg-white'}`}>
                  <h2 className={`text-2xl font-bold mb-6 ${isDarkMode ? 'text-white' : 'text-gray-800'}`}>
                    Configure Your Exercise
                  </h2>
                  <SynthSelector
                    selectedSynthesizer={selectedSynthesizer}
                    onSynthesizerChange={handleSynthesizerChange}
                    selectedExerciseType={selectedExerciseType}
                    onExerciseTypeChange={handleExerciseTypeChange}
                    selectedGenre={selectedGenre}
                    onGenreChange={handleGenreChange}
                  />
                </div>

                {/* Generate Button */}
                <div className="flex justify-center">
                  <button
                    onClick={() => {
                    console.log('BUTTON CLICK EVENT FIRED');
                    handleGenerateSoundDesign();
                  }}
                    disabled={soundDesignLoading}
                    className={`px-8 py-4 rounded-lg font-bold text-lg transition-all duration-200 ${
                      soundDesignLoading
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-gradient-to-r from-purple-600 to-pink-600 text-white hover:from-purple-700 hover:to-pink-700 shadow-lg transform hover:scale-105'
                    }`}
                  >
                    {soundDesignLoading ? (
                      <span className="flex items-center">
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Generating...
                      </span>
                    ) : (
                      '🎹 Generate Sound Design Exercise'
                    )}
                  </button>
                </div>

                {/* Sound Design Prompt Display */}
                {soundDesignPrompt && (
                  <SoundDesignPromptDisplay prompt={soundDesignPrompt} />
                )}

                {/* Error Display */}
                {soundDesignError && (
                  <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-red-700">
                          {soundDesignError}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Chord Progression Tab */}
            {activeTab === 'chord-progression' && (
              <>
                <div className={`mb-8 ${isDarkMode ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-lg p-6`}>
                  <h2 className={`text-2xl font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                    Generate Emotion Driven Chord Progressions
                  </h2>
                  <p className={`mb-6 ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                    Select 1 or 2 emotions to generate a chord progression with explanation of the selection and downloadable MIDI file.
                  </p>

                  {/* Emotion Selector */}
                  <div className="mb-6">
                    <h3 className={`text-lg font-semibold mb-3 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      Select Emotions {selectedEmotions.length > 0 && `(${selectedEmotions.length}/2)`}
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                      {emotions.map((emotion) => (
                        <button
                          key={emotion}
                          onClick={() => handleEmotionToggle(emotion)}
                          className={`px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                            selectedEmotions.includes(emotion)
                              ? isDarkMode
                                ? 'bg-blue-600 text-white ring-2 ring-blue-400'
                                : 'bg-blue-500 text-white ring-2 ring-blue-300'
                              : isDarkMode
                              ? 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                        >
                          {emotion}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Generate Button */}
                  <button
                    onClick={handleGenerateChordProgression}
                    disabled={chordProgressionLoading || selectedEmotions.length === 0}
                    className={`w-full py-4 rounded-lg font-semibold text-lg transition-all duration-200 ${
                      chordProgressionLoading || selectedEmotions.length === 0
                        ? isDarkMode
                          ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                          : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : isDarkMode
                        ? 'bg-blue-600 hover:bg-blue-700 text-white'
                        : 'bg-blue-500 hover:bg-blue-600 text-white'
                    }`}
                  >
                    {chordProgressionLoading ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Generating Progression...
                      </span>
                    ) : (
                      '🎼 Generate Chord Progression'
                    )}
                  </button>
                </div>

                {/* Chord Progression Display */}
                {chordProgression && (
                  <ChordProgressionPromptDisplay progression={chordProgression} />
                )}

                {/* Error Display */}
                {chordProgressionError && (
                  <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded-lg">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-red-700">
                          {chordProgressionError}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className={`mt-20 transition-colors duration-200 ${isDarkMode ? 'bg-gray-900' : 'bg-gray-800'}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <p className={isDarkMode ? 'text-gray-400' : 'text-gray-300'}>
              Built with React, Node.js & Python
            </p>
            <p className={`mt-2 text-sm ${isDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
              Powered by AWS, GCP, Azure | Monitored with Prometheus & OpenTelemetry
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;