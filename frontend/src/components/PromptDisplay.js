import React from 'react';

const PromptDisplay = ({ prompt, genres }) => {
  return (
    <div className="bg-white rounded-lg shadow-xl p-8 animate-fadeIn">
      <h3 className="text-2xl font-bold text-gray-800 mb-4">
        {prompt.title}
      </h3>
      
      <div className="mb-4">
        <span className="text-sm text-gray-600">Genres: </span>
        {genres.map((genre, index) => (
          <span key={genre} className="inline-block bg-indigo-100 text-indigo-800 px-2 py-1 rounded-md text-sm mr-2">
            {genre}
          </span>
        ))}
      </div>
      
      <p className="text-gray-700 leading-relaxed mb-6">
        {prompt.content}
      </p>
      
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
        <div>
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
    </div>
  );
};

export default PromptDisplay;