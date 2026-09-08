/**
 * Tailwind CSS Configuration
 * Custom configuration for AI Shopping Assistant
 */

// Configure Tailwind CSS
if (typeof tailwind !== 'undefined') {
  tailwind.config = {
    theme: {
      extend: {
        fontFamily: {
          'inter': ['Inter', 'sans-serif'],
          'poppins': ['Poppins', 'sans-serif'],
        },
        colors: {
          'ai-blue': '#3B82F6',
          'ai-purple': '#8B5CF6',
          'ai-gradient-start': '#667eea',
          'ai-gradient-end': '#764ba2',
          'chat-user': '#F0F9FF',
          'chat-bot': '#F8FAFC',
        },
        animation: {
          'gradient': 'gradient 6s ease infinite',
          'bounce-slow': 'bounce 2s infinite',
          'pulse-soft': 'pulse 3s ease-in-out infinite',
          'slide-up': 'slideUp 0.3s ease-out',
          'slide-in': 'slideIn 0.5s ease-out',
          'glow': 'glow 2s ease-in-out infinite alternate',
        },
        keyframes: {
          gradient: {
            '0%, 100%': {
              'background-size': '200% 200%',
              'background-position': 'left center'
            },
            '50%': {
              'background-size': '200% 200%',
              'background-position': 'right center'
            },
          },
          slideUp: {
            '0%': { transform: 'translateY(100%)', opacity: '0' },
            '100%': { transform: 'translateY(0)', opacity: '1' }
          },
          slideIn: {
            '0%': { transform: 'translateX(-100%)', opacity: '0' },
            '100%': { transform: 'translateX(0)', opacity: '1' }
          },
          glow: {
            '0%': { 'box-shadow': '0 0 5px #3B82F6, 0 0 10px #3B82F6, 0 0 15px #3B82F6' },
            '100%': { 'box-shadow': '0 0 10px #8B5CF6, 0 0 20px #8B5CF6, 0 0 30px #8B5CF6' }
          }
        }
      }
    }
  };
}