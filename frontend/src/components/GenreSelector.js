import React from 'react';

const GenreSelector = ({ genres, selectedGenres, onGenreToggle }) => {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
      {genres.map((genre) => (
        <button
          key={genre}
          onClick={() => onGenreToggle(genre)}
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
  );
};

export default GenreSelector;