import { useState } from 'react';

const EmojiPicker = ({ onEmojiSelect, isDarkMode }) => {
  const emojis = [
    '😀', '😃', '😄', '😁', '😊', '😇', '🙂', '🙃', '😉', '😌',
    '😍', '🥰', '😘', '😗', '😙', '😚', '😋', '😛', '😝', '😜',
    '🤪', '🤨', '🧐', '🤓', '😎', '🤩', '🥳', '😏', '😒', '😞',
    '😔', '😟', '😕', '🙁', '😣', '😖', '😫', '😩', '🥺', '😢',
    '😭', '😤', '😠', '😡', '🤬', '🤯', '😳', '🥵', '🥶', '😱',
    '👍', '👎', '👏', '🙌', '👐', '🤝', '🙏', '💪', '🎉', '🎊',
    '🏠', '🏡', '🏢', '🏬', '🏘️', '🏗️', '🏙️', '🗝️', '🔑', '💰',
    '💵', '💴', '💶', '💷', '💳', '📈', '📊', '✅', '❌', '❤️'
  ];

  const [isOpen, setIsOpen] = useState(false);

  const handleEmojiClick = (emoji) => {
    onEmojiSelect(emoji);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={`p-2 rounded-full transition-colors ${
          isDarkMode
            ? 'hover:bg-gray-600 text-gray-300'
            : 'hover:bg-gray-100 text-gray-500'
        }`}
        aria-label="Add emoji"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div
            className={`absolute bottom-full left-0 mb-2 p-3 rounded-2xl shadow-xl z-20 ${
              isDarkMode ? 'bg-gray-700' : 'bg-white'
            } border ${isDarkMode ? 'border-gray-600' : 'border-gray-200'}`}
            style={{ width: '300px', maxHeight: '250px' }}
          >
            <div className="grid grid-cols-8 gap-2 overflow-y-auto custom-scrollbar" style={{ maxHeight: '230px' }}>
              {emojis.map((emoji, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => handleEmojiClick(emoji)}
                  className={`text-2xl p-2 rounded-lg transition-colors ${
                    isDarkMode ? 'hover:bg-gray-600' : 'hover:bg-gray-100'
                  }`}
                >
                  {emoji}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default EmojiPicker;
