import { useState, useRef, useEffect } from 'react';
import { Send, Moon, Sun } from 'lucide-react';
import ChatBubble from './ChatBubble';
import EmojiPicker from './EmojiPicker';

const MessageContainer = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: 'Hello! How can I help you with real estate today?',
      timestamp: new Date().toISOString(),
      isUser: false,
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const simulateBotResponse = () => {
    setIsTyping(true);
    setTimeout(() => {
      const botResponses = [
        "That's interesting! Tell me more.",
        "I understand. How can I assist you further?",
        "Thanks for sharing that with me!",
        "Got it! What else would you like to know?",
        "I'm here to help. What's on your mind?",
      ];

      const randomResponse = botResponses[Math.floor(Math.random() * botResponses.length)];

      const botMessage = {
        id: Date.now(),
        text: randomResponse,
        timestamp: new Date().toISOString(),
        isUser: false,
      };

      setMessages((prevMessages) => [...prevMessages, botMessage]);
      setIsTyping(false);
    }, 1500);
  };

  const handleSendMessage = (e) => {
    e.preventDefault();

    if (inputValue.trim()) {
      const userMessage = {
        id: Date.now(),
        text: inputValue,
        timestamp: new Date().toISOString(),
        isUser: true,
      };

      setMessages([...messages, userMessage]);
      setInputValue('');

      simulateBotResponse(userMessage);
    }
  };

  const handleEmojiSelect = (emoji) => {
    setInputValue((prev) => prev + emoji);
  };

  return (
    <div className={`flex flex-col h-screen ${isDarkMode ? 'bg-gray-900' : 'bg-gray-100'} transition-colors`}>
      {/* Header */}
      <div className={`${isDarkMode ? 'bg-gray-800' : 'bg-blue-500'} px-6 py-5 transition-colors`}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Real Estate Chatbot</h1>
            <p className={`text-sm ${isDarkMode ? 'text-gray-300' : 'text-blue-100'} mt-0.5`}>Online</p>
          </div>
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className={`p-2.5 rounded-full transition-colors ${
              isDarkMode ? 'bg-gray-700 hover:bg-gray-600' : 'bg-blue-600 hover:bg-blue-700'
            }`}
            aria-label="Toggle theme"
          >
            {isDarkMode ? (
              <Sun className="w-5 h-5 text-yellow-300" />
            ) : (
              <Moon className="w-5 h-5 text-white" />
            )}
          </button>
        </div>
      </div>

      {/* Message Area */}
      <div className="flex-1 overflow-y-auto px-6 py-8 custom-scrollbar">
        <div className="space-y-4">
          {messages.map((message) => (
            <ChatBubble key={message.id} message={message} isUser={message.isUser} isDarkMode={isDarkMode} />
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className={`${isDarkMode ? 'bg-gray-700' : 'bg-gray-200'} px-4 py-3 rounded-3xl rounded-bl-sm transition-colors`}>
                <div className="flex gap-1.5">
                  <div className={`w-2 h-2 ${isDarkMode ? 'bg-gray-400' : 'bg-gray-500'} rounded-full animate-bounce`} style={{ animationDelay: '0ms' }}></div>
                  <div className={`w-2 h-2 ${isDarkMode ? 'bg-gray-400' : 'bg-gray-500'} rounded-full animate-bounce`} style={{ animationDelay: '150ms' }}></div>
                  <div className={`w-2 h-2 ${isDarkMode ? 'bg-gray-400' : 'bg-gray-500'} rounded-full animate-bounce`} style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}
        </div>
        <div ref={messagesEndRef} />
      </div>

      {/* Input Section */}
      <div className={`${isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-t px-6 py-5 transition-colors`}>
        <form onSubmit={handleSendMessage} className="flex gap-3 items-center">
          <EmojiPicker onEmojiSelect={handleEmojiSelect} isDarkMode={isDarkMode} />
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type a message about real estate..."
            className={`flex-1 px-5 py-4 ${
              isDarkMode
                ? 'bg-gray-700 border-gray-600 text-white placeholder:text-gray-400'
                : 'bg-white border-gray-300 text-gray-900 placeholder:text-gray-400'
            } border rounded-full text-base focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent transition-all`}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage(e);
              }
            }}
          />
          <button
            type="submit"
            disabled={!inputValue.trim()}
            className="p-4 bg-blue-500 text-white rounded-full hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center shadow-lg"
          >
            <Send className="w-6 h-6" />
          </button>
        </form>
      </div>
    </div>
  );
};

export default MessageContainer;
