const ChatBubble = ({ message, isUser = false, isDarkMode = false }) => {
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className="flex flex-col max-w-[70%]">
        <div
          className={`px-5 py-3.5 transition-colors ${
            isUser
              ? 'bg-blue-500 text-white rounded-3xl rounded-br-sm'
              : isDarkMode
              ? 'bg-gray-700 text-gray-100 rounded-3xl rounded-bl-sm'
              : 'bg-gray-200 text-gray-900 rounded-3xl rounded-bl-sm'
          }`}
        >
          <p className="text-base leading-relaxed break-words">{message.text}</p>
        </div>
        <p className={`text-xs mt-1.5 px-2 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'} ${isUser ? 'text-right' : 'text-left'}`}>
          {formatTimestamp(message.timestamp)}
        </p>
      </div>
    </div>
  );
};

export default ChatBubble;
