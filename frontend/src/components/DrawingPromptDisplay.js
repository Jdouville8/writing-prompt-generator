import React, { useState, useEffect } from 'react';
import { useTheme } from '../contexts/ThemeContext';

function DrawingPromptDisplay({ prompt }) {
  const { isDarkMode } = useTheme();
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [isTimerRunning, setIsTimerRunning] = useState(false);
  const [timerStarted, setTimerStarted] = useState(false);
  const [uploadedImage, setUploadedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);
  const [feedbackError, setFeedbackError] = useState(null);

  // Render markdown-formatted feedback
  const renderFeedback = (text) => {
    if (!text) return null;

    const lines = text.split('\n');
    const elements = [];

    lines.forEach((line, index) => {
      const trimmedLine = line.trim();

      // Empty lines
      if (trimmedLine === '') {
        elements.push(<div key={`space-${index}`} className="h-3"></div>);
        return;
      }

      // H3 headings (###)
      if (trimmedLine.startsWith('###')) {
        const headingText = trimmedLine.replace(/^###\s*/, '');
        const parsedHeading = parseInlineMarkdown(headingText);
        elements.push(
          <h3 key={index} className={`text-lg font-bold mt-4 mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            {parsedHeading}
          </h3>
        );
        return;
      }

      // H4 headings (####)
      if (trimmedLine.startsWith('####')) {
        const headingText = trimmedLine.replace(/^####\s*/, '');
        const parsedHeading = parseInlineMarkdown(headingText);
        elements.push(
          <h4 key={index} className={`text-base font-semibold mt-3 mb-1 ${isDarkMode ? 'text-gray-200' : 'text-gray-800'}`}>
            {parsedHeading}
          </h4>
        );
        return;
      }

      // Bulleted lists
      if (trimmedLine.startsWith('-') || trimmedLine.startsWith('•')) {
        const bulletText = trimmedLine.replace(/^[-•]\s*/, '');
        const parsedBullet = parseInlineMarkdown(bulletText);
        elements.push(
          <div key={index} className="flex items-start ml-4 mb-1">
            <span className={`mr-2 ${isDarkMode ? 'text-purple-300' : 'text-purple-600'}`}>•</span>
            <span className={isDarkMode ? 'text-gray-100' : 'text-gray-800'}>{parsedBullet}</span>
          </div>
        );
        return;
      }

      // Numbered lists
      if (trimmedLine.match(/^\d+\./)) {
        const parsedLine = parseInlineMarkdown(trimmedLine);
        elements.push(
          <div key={index} className={`ml-4 mb-1 ${isDarkMode ? 'text-gray-100' : 'text-gray-800'}`}>
            {parsedLine}
          </div>
        );
        return;
      }

      // Regular paragraphs
      const parsedLine = parseInlineMarkdown(line);
      elements.push(
        <p key={index} className={`mb-2 ${isDarkMode ? 'text-gray-100' : 'text-gray-800'}`}>
          {parsedLine}
        </p>
      );
    });

    return elements;
  };

  // Parse inline markdown (bold)
  const parseInlineMarkdown = (text) => {
    if (!text) return null;
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        const boldText = part.slice(2, -2);
        return <strong key={index} className={`font-bold ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>{boldText}</strong>;
      }
      return <span key={index}>{part}</span>;
    });
  };

  useEffect(() => {
    if (prompt?.estimatedTime) {
      const minutes = parseInt(prompt.estimatedTime);
      setTimeRemaining(minutes * 60);
      setIsTimerRunning(false);
      setTimerStarted(false);
    }
  }, [prompt]);

  useEffect(() => {
    let interval;
    if (isTimerRunning && timeRemaining > 0) {
      interval = setInterval(() => {
        setTimeRemaining((prev) => {
          if (prev <= 1) {
            setIsTimerRunning(false);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isTimerRunning, timeRemaining]);

  const toggleTimer = () => {
    setIsTimerRunning(!isTimerRunning);
    if (!timerStarted) {
      setTimerStarted(true);
    }
  };

  const resetTimer = () => {
    if (prompt?.estimatedTime) {
      const minutes = parseInt(prompt.estimatedTime);
      setTimeRemaining(minutes * 60);
      setIsTimerRunning(false);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Check file type
    if (file.type !== 'image/jpeg' && file.type !== 'image/png') {
      setFeedbackError('Please upload a JPG or PNG image');
      e.target.value = ''; // Clear the input
      return;
    }

    // Check file size (20MB = 20 * 1024 * 1024 bytes)
    const maxSize = 20 * 1024 * 1024;
    if (file.size > maxSize) {
      setFeedbackError('Image file is too large. Please upload an image smaller than 20MB.');
      e.target.value = ''; // Clear the input
      return;
    }

    setUploadedImage(file);

    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setImagePreview(reader.result);
    };
    reader.readAsDataURL(file);

    // Clear previous feedback
    setFeedback(null);
    setFeedbackError(null);
  };

  const handleRemoveImage = () => {
    setUploadedImage(null);
    setImagePreview(null);
    setFeedback(null);
    setFeedbackError(null);
  };

  const handleSubmitForFeedback = async () => {
    if (!uploadedImage) return;

    setFeedbackLoading(true);
    setFeedbackError(null);
    setFeedback(null);

    try {
      // Convert image to base64
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64Image = reader.result;

        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/drawing/feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            image: base64Image,
            exercise: prompt.content,
            skills: prompt.skills,
            difficulty: prompt.difficulty
          })
        });

        if (!response.ok) {
          throw new Error('Failed to get feedback');
        }

        const data = await response.json();
        setFeedback(data.feedback);
        setFeedbackLoading(false);
      };

      reader.onerror = () => {
        setFeedbackError('Failed to read image file');
        setFeedbackLoading(false);
      };

      reader.readAsDataURL(uploadedImage);
    } catch (error) {
      console.error('Feedback generation failed:', error);
      setFeedbackError(error.message);
      setFeedbackLoading(false);
    }
  };

  if (!prompt) return null;

  return (
    <div className={`bg-gradient-to-br rounded-lg shadow-xl p-8 ${isDarkMode ? 'from-gray-800 to-gray-900' : 'from-purple-50 to-pink-50'}`}>
      {/* Header with Title and Metadata */}
      <div className="mb-6">
        <h2 className={`text-3xl font-bold mb-2 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
          {prompt.title}
        </h2>
        <div className="flex flex-wrap gap-3 text-sm">
          <span className={`px-3 py-1 rounded-full font-medium ${isDarkMode ? 'bg-purple-900 text-purple-200' : 'bg-purple-100 text-purple-800'}`}>
            {prompt.difficulty}
          </span>
          <span className={`px-3 py-1 rounded-full font-medium ${isDarkMode ? 'bg-pink-900 text-pink-200' : 'bg-pink-100 text-pink-800'}`}>
            ⏱ {prompt.estimatedTime}
          </span>
          {prompt.skills && prompt.skills.map((skill, idx) => (
            <span key={idx} className={`px-3 py-1 rounded-full font-medium ${isDarkMode ? 'bg-indigo-900 text-indigo-200' : 'bg-indigo-100 text-indigo-800'}`}>
              🎨 {skill}
            </span>
          ))}
        </div>
      </div>

      {/* Timer */}
      {timeRemaining !== null && (
        <div className={`mb-6 p-4 rounded-lg shadow-md ${isDarkMode ? 'bg-gray-800' : 'bg-white'}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm mb-1 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Time Remaining</p>
              <p className={`text-4xl font-bold ${timeRemaining === 0 ? 'text-red-500' : isDarkMode ? 'text-white' : 'text-gray-900'}`}>
                {formatTime(timeRemaining)}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={toggleTimer}
                className={`px-6 py-3 rounded-lg font-semibold transition-colors ${
                  isTimerRunning
                    ? 'bg-yellow-500 hover:bg-yellow-600 text-white'
                    : 'bg-green-500 hover:bg-green-600 text-white'
                }`}
              >
                {isTimerRunning ? '⏸ Pause' : timerStarted ? '▶ Resume' : '▶ Start'}
              </button>
              <button
                onClick={resetTimer}
                className="px-6 py-3 bg-gray-500 hover:bg-gray-600 text-white rounded-lg font-semibold transition-colors"
              >
                🔄 Reset
              </button>
            </div>
          </div>
          {timeRemaining === 0 && (
            <p className="mt-2 text-red-500 font-semibold">⏰ Time's up!</p>
          )}
        </div>
      )}

      {/* Exercise Content */}
      <div className={`prose prose-lg max-w-none ${isDarkMode ? 'prose-invert' : ''}`}>
        <div className={`rounded-lg p-6 shadow-md whitespace-pre-wrap ${isDarkMode ? 'bg-gray-800 text-gray-100' : 'bg-white text-gray-900'}`}>
          {prompt.content}
        </div>
      </div>

      {/* Tips Section */}
      {prompt.tips && prompt.tips.length > 0 && (
        <div className={`mt-6 p-6 bg-gradient-to-r rounded-lg ${isDarkMode ? 'from-purple-900 to-pink-900' : 'from-purple-100 to-pink-100'}`}>
          <h3 className={`text-xl font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
            💡 Drawing Tips
          </h3>
          <ul className="space-y-2">
            {prompt.tips.map((tip, index) => (
              <li key={index} className="flex items-start">
                <span className={`mr-2 ${isDarkMode ? 'text-purple-400' : 'text-purple-600'}`}>▸</span>
                <span className={isDarkMode ? 'text-gray-200' : 'text-gray-800'}>{tip}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Image Upload Section */}
      <div className={`mt-8 border-t-2 pt-6 ${isDarkMode ? 'border-gray-600' : 'border-gray-300'}`}>
        <h3 className={`text-xl font-bold mb-4 ${isDarkMode ? 'text-white' : 'text-gray-900'}`}>
          📸 Submit Your Drawing for Feedback
        </h3>

        {!imagePreview ? (
          <div className={`border-2 border-dashed rounded-lg p-8 text-center ${isDarkMode ? 'border-gray-600' : 'border-gray-300'}`}>
            <label htmlFor="drawing-upload" className="cursor-pointer">
              <div className="mb-4">
                <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                  <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className={`mb-2 ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                Click to upload your drawing
              </p>
              <p className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                JPG or PNG (max 20MB)
              </p>
              <input
                id="drawing-upload"
                type="file"
                accept="image/jpeg,image/png"
                onChange={handleImageUpload}
                className="hidden"
              />
            </label>
          </div>
        ) : (
          <div>
            {/* Image Preview */}
            <div className="relative mb-4">
              <img
                src={imagePreview}
                alt="Drawing preview"
                className={`w-full max-h-96 object-contain rounded-lg ${isDarkMode ? 'bg-gray-700' : 'bg-white'}`}
              />
              <button
                onClick={handleRemoveImage}
                className="absolute top-2 right-2 bg-red-500 hover:bg-red-600 text-white rounded-full p-2 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Submit Button */}
            <button
              onClick={handleSubmitForFeedback}
              disabled={feedbackLoading}
              className={`w-full py-3 px-6 rounded-lg font-semibold transition-all duration-200 ${
                feedbackLoading
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-purple-600 hover:bg-purple-700 text-white cursor-pointer'
              }`}
            >
              {feedbackLoading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Analyzing Your Drawing...
                </span>
              ) : (
                '🎨 Get AI Feedback'
              )}
            </button>
          </div>
        )}

        {/* Error Display */}
        {feedbackError && (
          <div className={`mt-4 p-4 rounded-lg ${isDarkMode ? 'bg-red-900' : 'bg-red-100'}`}>
            <p className={isDarkMode ? 'text-red-200' : 'text-red-800'}>
              Error getting feedback: {feedbackError}
            </p>
          </div>
        )}

        {/* Feedback Display */}
        {feedback && (
          <div className={`mt-6 p-6 rounded-lg bg-gradient-to-br ${isDarkMode ? 'from-purple-950 to-pink-950' : 'from-purple-900 to-pink-900'}`}>
            <h4 className="text-xl font-bold mb-4 text-white">
              ✨ AI Feedback on Your Drawing
            </h4>
            <div className="leading-relaxed">
              {renderFeedback(feedback)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default DrawingPromptDisplay;
