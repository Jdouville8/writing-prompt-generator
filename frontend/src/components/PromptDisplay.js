import React, { useState, useRef, useEffect } from 'react';

const PromptDisplay = ({ prompt, genres }) => {
  const [writingText, setWritingText] = useState('');
  const [wordCount, setWordCount] = useState(0);
  const textareaRef = useRef(null);

  useEffect(() => {
    const text = writingText.trim();
    if (text === '') {
      setWordCount(0);
    } else {
      const words = text.split(/\s+/).filter(word => word.length > 0);
      setWordCount(words.length);
    }
  }, [writingText]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [writingText]);

  const parseMarkdown = (text) => {
    if (!text) return null;
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        const boldText = part.slice(2, -2);
        return <strong key={index} className="font-semibold text-gray-900">{boldText}</strong>;
      }
      return <span key={index}>{part}</span>;
    });
  };

  const renderContent = () => {
    if (!prompt.content) return null;
    const lines = prompt.content.split('\n');
    const elements = [];
    
    lines.forEach((line, index) => {
      const trimmedLine = line.trim();
      if (trimmedLine === '') {
        elements.push(<div key={`space-${index}`} className="h-4"></div>);
        return;
      }
      const isSectionHeader = trimmedLine.match(/^\*\*[^*]+\*\*:/);
      if (isSectionHeader && elements.length > 0) {
        elements.push(<div key={`space-before-${index}`} className="h-3"></div>);
      }
      elements.push(
        <div key={index} className={trimmedLine.match(/^\d+\./) ? 'ml-4' : ''}>
          {parseMarkdown(line)}
        </div>
      );
      if (isSectionHeader) {
        elements.push(<div key={`space-after-${index}`} className="h-1"></div>);
      }
    });
    return elements;
  };

  const handleClearText = () => {
    if (window.confirm('Are you sure you want to clear all your writing?')) {
      setWritingText('');
    }
  };

  const handleDownload = () => {
    const element = document.createElement('a');
    const file = new Blob([writingText], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = 'my-writing.txt';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="bg-white rounded-lg shadow-xl p-8 animate-fadeIn">
      <h3 className="text-2xl font-bold text-gray-800 mb-4">{prompt.title}</h3>
      
      <div className="mb-4">
        <span className="text-sm text-gray-600">Genres: </span>
        {genres.map((genre) => (
          <span key={genre} className="inline-block bg-indigo-100 text-indigo-800 px-2 py-1 rounded-md text-sm mr-2">
            {genre}
          </span>
        ))}
      </div>
      
      <div className="text-gray-700 leading-relaxed mb-6">{renderContent()}</div>
      
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-sm text-gray-600">Difficulty</p>
          <p className="font-semibold">{prompt.difficulty}</p>
        </div>
        <div className="bg-gray-50 p-3 rounded">
          <p className="text-sm text-gray-600">Suggested Word Count</p>
          <p className="font-semibold">{prompt.wordCount} words</p>
        </div>
      </div>
      
      {prompt.tips && prompt.tips.length > 0 && (
        <div className="mb-8">
          <h4 className="font-semibold text-gray-800 mb-2">Writing Tips:</h4>
          <ul className="space-y-2">
            {prompt.tips.map((tip, index) => (
              <li key={index} className="flex items-start">
                <span className="text-indigo-600 mr-2">•</span>
                <span className="text-gray-600 text-sm">{tip}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="border-t-2 border-gray-200 pt-6">
        <div className="flex justify-between items-center mb-3">
          <h4 className="font-semibold text-gray-800 text-lg">Your Response:</h4>
          <div className="flex items-center gap-4">
            <div className="text-sm">
              <span className={`font-semibold $${wordCount >= prompt.wordCount ? 'text-green-600' : 'text-gray-600'}`}>
                {wordCount}
              </span>
              <span className="text-gray-500"> / {prompt.wordCount} words</span>
            </div>
            {writingText && (
              <>
                <button onClick={handleDownload} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">
                  💾 Download
                </button>
                <button onClick={handleClearText} className="text-sm text-red-600 hover:text-red-800 font-medium">
                  🗑️ Clear
                </button>
              </>
            )}
          </div>
        </div>

        <div className="relative">
          <textarea
            ref={textareaRef}
            value={writingText}
            onChange={(e) => setWritingText(e.target.value)}
            placeholder="Start writing here... The text box will expand as you type."
            className="w-full p-4 border-2 border-gray-300 rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all resize-none overflow-hidden font-serif text-base leading-relaxed"
            style={{ minHeight: '200px' }}
          />
          {writingText === '' && (
            <div className="absolute top-20 left-0 right-0 text-center text-gray-400 pointer-events-none">
              <p className="text-sm italic">Tip: Just start writing!</p>
            </div>
          )}
        </div>

        {wordCount > 0 && (
          <div className="mt-3 flex justify-between items-center text-sm text-gray-500">
            <div>Characters: {writingText.length}</div>
            <div>
              {wordCount >= prompt.wordCount ? (
                <span className="text-green-600 font-medium">✓ Target reached!</span>
              ) : (
                <span>{prompt.wordCount - wordCount} words to go</span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PromptDisplay;
