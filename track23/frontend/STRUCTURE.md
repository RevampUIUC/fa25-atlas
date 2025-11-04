# Project Structure

```
src/
├── assets/          # Static assets (images, fonts, etc.)
├── components/      # Reusable UI components
│   └── Button.jsx   # Example button component
├── hooks/           # Custom React hooks
│   └── useLocalStorage.js  # Example custom hook
├── pages/           # Page components
│   └── Home.jsx     # Home page
├── utils/           # Utility functions
│   └── helpers.js   # Helper functions
├── App.jsx          # Main App component
├── main.jsx         # Application entry point
└── index.css        # Global styles with Tailwind
```

## Folder Descriptions

### `/components`
Reusable UI components that can be used across different pages.
Example: Button, Card, Modal, Navbar, etc.

### `/pages`
Top-level page components that represent different routes/views.
Example: Home, About, Dashboard, Profile, etc.

### `/utils`
Utility functions and helper methods.
Example: API calls, formatters, validators, constants, etc.

### `/hooks`
Custom React hooks for shared logic.
Example: useLocalStorage, useFetch, useDebounce, etc.

### `/assets`
Static files like images, fonts, icons, etc.

## Usage Examples

### Importing a component:
```jsx
import Button from './components/Button';
```

### Using a utility function:
```jsx
import { formatDate } from './utils/helpers';
```

### Using a custom hook:
```jsx
import useLocalStorage from './hooks/useLocalStorage';
```
