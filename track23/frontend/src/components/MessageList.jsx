import React from 'react';

const MessageList = ({ messages = [] }) => {
  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
          <p className="mt-2 text-gray-400 text-lg">No messages yet</p>
          <p className="text-gray-400 text-sm">Start a conversation!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {messages.map((message, index) => {
        const showAvatar =
          index === messages.length - 1 ||
          messages[index + 1]?.sender !== message.sender;

        return (
          <MessageBubble
            key={message.id}
            message={message}
            showAvatar={showAvatar}
          />
        );
      })}
    </div>
  );
};

const MessageBubble = ({ message, showAvatar }) => {
  const isOwnMessage = message.sender === 'me';

  return (
    <div className={`flex items-end gap-2 ${isOwnMessage ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      {showAvatar && !isOwnMessage && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-sm font-semibold flex-shrink-0">
          {message.senderName?.[0]?.toUpperCase() || 'U'}
        </div>
      )}
      {!showAvatar && !isOwnMessage && <div className="w-8" />}

      {/* Message Content */}
      <div className={`flex flex-col ${isOwnMessage ? 'items-end' : 'items-start'} max-w-md`}>
        {!isOwnMessage && showAvatar && (
          <p className="text-xs font-semibold text-gray-600 mb-1 px-1">
            {message.senderName}
          </p>
        )}
        
        <div
          className={`px-4 py-2 rounded-2xl ${
            isOwnMessage
              ? 'bg-blue-500 text-white rounded-br-sm'
              : 'bg-white text-gray-800 rounded-bl-sm shadow-sm border border-gray-100'
          }`}
        >
          <p className="text-sm leading-relaxed">{message.text}</p>
        </div>
        
        <p
          className={`text-xs mt-1 px-1 ${
            isOwnMessage ? 'text-gray-400' : 'text-gray-400'
          }`}
        >
          {message.timestamp}
        </p>
      </div>

      {/* Own message avatar space */}
      {showAvatar && isOwnMessage && <div className="w-8" />}
      {!showAvatar && isOwnMessage && <div className="w-8" />}
    </div>
  );
};

export default MessageList;
