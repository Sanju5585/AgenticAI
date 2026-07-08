/**
 * Voice Search Integration for E-commerce AI Assistant
 * Provides speech-to-text functionality with visual feedback
 */

class VoiceSearch {
    constructor() {
        this.recognition = null;
        this.isListening = false;
        this.micButton = null;
        this.statusIndicator = null;
        this.transcript = '';
        
        this.initializeVoiceSearch();
        this.createMicButton();
    }

    initializeVoiceSearch() {
        // Check for browser support
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.warn('Voice search not supported in this browser');
            this.showUnsupportedMessage();
            return;
        }

        // Initialize Speech Recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        // Configure recognition settings
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US'; // Default to English, can be changed
        this.recognition.maxAlternatives = 1;

        this.setupEventListeners();
    }

    setupEventListeners() {
        if (!this.recognition) return;

        // When speech recognition starts
        this.recognition.onstart = () => {
            console.log('Voice search started');
            this.isListening = true;
            this.updateMicButtonState();
            this.showListeningIndicator();
        };

        // When speech is detected
        this.recognition.onresult = (event) => {
            let finalTranscript = '';
            let interimTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }

            this.transcript = finalTranscript || interimTranscript;
            this.updateTranscriptDisplay(finalTranscript, interimTranscript);

            if (finalTranscript) {
                this.processVoiceQuery(finalTranscript.trim());
            }
        };

        // When speech recognition ends
        this.recognition.onend = () => {
            console.log('Voice search ended');
            this.isListening = false;
            this.updateMicButtonState();
            this.hideListeningIndicator();
        };

        // Handle errors
        this.recognition.onerror = (event) => {
            console.error('Voice search error:', event.error);
            this.handleVoiceError(event.error);
            this.isListening = false;
            this.updateMicButtonState();
        };
    }

    createMicButton() {
        // Create voice search container
        const voiceContainer = document.createElement('div');
        voiceContainer.className = 'voice-search-container';
        voiceContainer.innerHTML = `
            <div class="voice-search-wrapper">
                <!-- Visual Search Button (first/left) -->
                <button id="image-upload-btn" class="voice-search-btn visual-search-btn" title="Visual Search">
                    <i class="fas fa-camera"></i>
                    <span class="voice-btn-text">Visual</span>
                </button>

                <!-- Microphone Button -->
                <button id="voice-search-btn" class="voice-search-btn" title="Voice Search">
                    <i class="fas fa-microphone"></i>
                    <span class="voice-btn-text">Voice</span>
                </button>

                <!-- Status Indicator -->
                <div id="voice-status" class="voice-status hidden">
                    <div class="listening-animation">
                        <div class="sound-wave"></div>
                        <div class="sound-wave"></div>
                        <div class="sound-wave"></div>
                    </div>
                    <span class="status-text">Listening...</span>
                </div>

                <!-- Transcript Display -->
                <div id="voice-transcript" class="voice-transcript hidden">
                    <div class="transcript-content">
                        <span class="transcript-final"></span>
                        <span class="transcript-interim"></span>
                    </div>
                </div>

                <!-- Hidden File Input -->
                <input type="file" id="image-upload-input" accept="image/*" class="hidden" />

                <!-- Language Selector -->
                <select id="voice-language" class="voice-language" title="Voice Language">
                    <option value="en-US">🇺🇸 English</option>
                    <option value="hi-IN">🇮🇳 हिंदी</option>
                    <option value="es-ES">🇪🇸 Español</option>
                    <option value="fr-FR">🇫🇷 Français</option>
                    <option value="de-DE">🇩🇪 Deutsch</option>
                    <option value="zh-CN">🇨🇳 中文</option>
                    <option value="ja-JP">🇯🇵 日本語</option>
                </select>
            </div>
        `;

        // Add CSS styles
        this.addVoiceSearchStyles();

        // Insert the voice search container
        this.insertVoiceSearchUI(voiceContainer);

        // Setup button event listeners
        this.micButton = document.getElementById('voice-search-btn');
        this.statusIndicator = document.getElementById('voice-status');
        
        if (this.micButton) {
            this.micButton.addEventListener('click', () => this.toggleVoiceSearch());
        }

        // Setup visual search button
        const imageButton = document.getElementById('image-upload-btn');
        const imageInput = document.getElementById('image-upload-input');
        
        if (imageButton && imageInput) {
            imageButton.addEventListener('click', () => {
                if (window.isVisualSearchInProgress) {
                    if (typeof window.showNotification === 'function') {
                        window.showNotification('Image search in progress. Please wait a moment.', 'info');
                    }
                    return;
                }
                imageInput.click();
            });
            
            imageInput.addEventListener('change', (event) => {
                const file = event.target.files && event.target.files[0];
                if (file && typeof window.handleVisualSearchFile === 'function') {
                    window.handleVisualSearchFile(file);
                }
                imageInput.value = '';
            });
        }

        // Language selector
        const languageSelector = document.getElementById('voice-language');
        if (languageSelector) {
            languageSelector.addEventListener('change', (e) => {
                if (this.recognition) {
                    this.recognition.lang = e.target.value;
                }
            });
        }
    }

    addVoiceSearchStyles() {
        const styles = `
            <style id="voice-search-styles">
                .voice-search-container {
                    position: relative;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    margin-bottom: 16px;
                    padding: 0;
                }

                .voice-search-wrapper {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    flex-wrap: wrap;
                    width: 100%;
                }

                .voice-search-btn {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    background: #D32029;
                    color: white;
                    border: none;
                    padding: 12px 16px;
                    border-radius: 25px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 600;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 15px rgba(211, 32, 41, 0.3);
                    position: relative;
                    overflow: hidden;
                }

                .voice-search-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 6px 20px rgba(211, 32, 41, 0.45);
                    background: #b01a20;
                }

                .voice-search-btn.listening {
                    background: #b01a20;
                    animation: pulse 1.5s infinite;
                }

                .voice-search-btn.processing {
                    background: #003F7A;
                }

                .visual-search-btn {
                    background: #00529B;
                }

                .visual-search-btn:hover {
                    background: #003F7A;
                    box-shadow: 0 6px 20px rgba(0, 82, 155, 0.45);
                }

                @keyframes pulse {
                    0% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.7); }
                    70% { box-shadow: 0 0 0 10px rgba(255, 107, 107, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(255, 107, 107, 0); }
                }

                .voice-status {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    background: rgba(255, 107, 107, 0.1);
                    padding: 8px 12px;
                    border-radius: 20px;
                    border: 2px solid rgba(255, 107, 107, 0.3);
                }

                .listening-animation {
                    display: flex;
                    gap: 3px;
                    align-items: center;
                }

                .sound-wave {
                    width: 3px;
                    height: 20px;
                    background: #ff6b6b;
                    border-radius: 2px;
                    animation: wave 0.8s ease-in-out infinite alternate;
                }

                .sound-wave:nth-child(2) {
                    animation-delay: 0.2s;
                }

                .sound-wave:nth-child(3) {
                    animation-delay: 0.4s;
                }

                @keyframes wave {
                    0% { height: 8px; }
                    100% { height: 20px; }
                }

                .status-text {
                    color: #ff6b6b;
                    font-weight: 600;
                    font-size: 14px;
                }

                .voice-transcript {
                    background: rgba(76, 175, 80, 0.1);
                    padding: 8px 12px;
                    border-radius: 15px;
                    border: 2px solid rgba(76, 175, 80, 0.3);
                    max-width: 300px;
                    word-wrap: break-word;
                }

                .transcript-final {
                    color: #2e7d32;
                    font-weight: 600;
                }

                .transcript-interim {
                    color: #4caf50;
                    font-style: italic;
                    opacity: 0.7;
                }

                .voice-language {
                    padding: 8px 12px;
                    border-radius: 15px;
                    border: 2px solid #ddd;
                    background: white;
                    font-size: 12px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }

                .voice-language:hover, .voice-language:focus {
                    border-color: #667eea;
                    outline: none;
                    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
                }

                .hidden {
                    display: none !important;
                }

                .voice-unsupported {
                    background: rgba(255, 193, 7, 0.1);
                    color: #f57c00;
                    padding: 10px 15px;
                    border-radius: 15px;
                    border: 2px solid rgba(255, 193, 7, 0.3);
                    font-size: 14px;
                    text-align: center;
                }

                /* Responsive design */
                @media (max-width: 768px) {
                    .voice-search-container {
                        margin-bottom: 12px;
                    }
                    
                    .voice-search-wrapper {
                        flex-direction: row;
                        align-items: center;
                        gap: 8px;
                    }
                    
                    .voice-search-btn {
                        justify-content: center;
                        padding: 10px 14px;
                        font-size: 13px;
                    }
                    
                    .voice-language {
                        padding: 6px 10px;
                        font-size: 11px;
                    }
                    
                    .voice-transcript {
                        max-width: 100%;
                    }
                }
            </style>
        `;
        
        // Add styles to head
        if (!document.getElementById('voice-search-styles')) {
            document.head.insertAdjacentHTML('beforeend', styles);
        }
    }

    insertVoiceSearchUI(voiceContainer) {
        // Find the chat input area container (the parent div with p-6 bg-white/70 classes)
        const chatInputArea = document.querySelector('.p-6.bg-white\\/70') || 
                             document.querySelector('#query')?.closest('.p-6');
        
        if (chatInputArea) {
            // Insert at the beginning of the chat input area (before the flex container)
            const flexContainer = chatInputArea.querySelector('.flex.items-stretch');
            if (flexContainer) {
                chatInputArea.insertBefore(voiceContainer, flexContainer);
            } else {
                chatInputArea.insertBefore(voiceContainer, chatInputArea.firstChild);
            }
        } else {
            // Fallback: Try to find the query input and insert before it
            const queryInput = document.getElementById('query');
            if (queryInput && queryInput.parentNode) {
                queryInput.parentNode.parentNode.insertBefore(voiceContainer, queryInput.parentNode);
            }
        }
    }

    toggleVoiceSearch() {
        if (!this.recognition) {
            this.showUnsupportedMessage();
            return;
        }

        if (this.isListening) {
            this.stopListening();
        } else {
            this.startListening();
        }
    }

    startListening() {
        try {
            this.transcript = '';
            this.recognition.start();
        } catch (error) {
            console.error('Error starting voice recognition:', error);
            this.handleVoiceError(error.message);
        }
    }

    stopListening() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
        }
    }

    updateMicButtonState() {
        if (!this.micButton) return;

        const icon = this.micButton.querySelector('i');
        const text = this.micButton.querySelector('.voice-btn-text');

        if (this.isListening) {
            this.micButton.classList.add('listening');
            icon.className = 'fas fa-stop';
            text.textContent = 'Stop';
            this.micButton.title = 'Stop Voice Search';
        } else {
            this.micButton.classList.remove('listening', 'processing');
            icon.className = 'fas fa-microphone';
            text.textContent = 'Voice';
            this.micButton.title = 'Start Voice Search';
        }
    }

    showListeningIndicator() {
        if (this.statusIndicator) {
            this.statusIndicator.classList.remove('hidden');
        }
    }

    hideListeningIndicator() {
        if (this.statusIndicator) {
            this.statusIndicator.classList.add('hidden');
        }
        
        // Hide transcript after a delay
        setTimeout(() => {
            const transcriptDisplay = document.getElementById('voice-transcript');
            if (transcriptDisplay) {
                transcriptDisplay.classList.add('hidden');
            }
        }, 3000);
    }

    updateTranscriptDisplay(finalText, interimText) {
        const transcriptDisplay = document.getElementById('voice-transcript');
        if (!transcriptDisplay) return;

        const finalSpan = transcriptDisplay.querySelector('.transcript-final');
        const interimSpan = transcriptDisplay.querySelector('.transcript-interim');

        if (finalSpan) finalSpan.textContent = finalText;
        if (interimSpan) interimSpan.textContent = interimText;

        if (finalText || interimText) {
            transcriptDisplay.classList.remove('hidden');
        }
    }

    processVoiceQuery(query) {
        console.log('Processing voice query:', query);
        
        // Update button state to show processing
        this.micButton.classList.add('processing');
        
        // Send the voice query to the chat system
        this.sendVoiceQueryToChat(query);
        
        // Reset button state after processing
        setTimeout(() => {
            this.micButton.classList.remove('processing');
        }, 2000);
    }

    sendVoiceQueryToChat(query) {
        // Find the specific query input field
        const queryInput = document.getElementById('query');
        
        if (queryInput) {
            // Set the voice query in the input field
            queryInput.value = query;
            
            // Trigger input event to update any listeners
            queryInput.dispatchEvent(new Event('input', { bubbles: true }));
            
            // Add visual indicator that this is a voice query
            this.showVoiceQueryIndicator(query);
            
            // Call the existing submitQuery function if available
            if (typeof window.submitQuery === 'function') {
                window.submitQuery();
            } else {
                // Fallback: trigger the onclick of the send button
                const sendButton = document.querySelector('[onclick="submitQuery()"]');
                if (sendButton) {
                    sendButton.click();
                } else {
                    console.error('Could not find submitQuery function or send button');
                    this.showVoiceQueryFallback(query);
                }
            }
        } else {
            console.error('Could not find query input field');
            this.showVoiceQueryFallback(query);
        }
    }

    showVoiceQueryIndicator(query) {
        // Create a temporary visual indicator
        const indicator = document.createElement('div');
        indicator.className = 'voice-query-indicator';
        indicator.innerHTML = `
            <div class="voice-query-content">
                <i class="fas fa-microphone"></i>
                <span>Voice: "${query}"</span>
            </div>
        `;
        
        // Add styles for the indicator
        if (!document.getElementById('voice-query-indicator-styles')) {
            const styles = `
                <style id="voice-query-indicator-styles">
                    .voice-query-indicator {
                        position: fixed;
                        top: 20px;
                        right: 20px;
                        background: linear-gradient(135deg, #4caf50 0%, #45a049 100%);
                        color: white;
                        padding: 12px 20px;
                        border-radius: 25px;
                        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
                        z-index: 10000;
                        animation: slideInRight 0.3s ease-out;
                    }
                    
                    .voice-query-content {
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-weight: 600;
                        font-size: 14px;
                    }
                    
                    @keyframes slideInRight {
                        from { transform: translateX(100%); opacity: 0; }
                        to { transform: translateX(0); opacity: 1; }
                    }
                </style>
            `;
            document.head.insertAdjacentHTML('beforeend', styles);
        }
        
        document.body.appendChild(indicator);
        
        // Remove the indicator after 3 seconds
        setTimeout(() => {
            if (indicator.parentNode) {
                indicator.remove();
            }
        }, 3000);
    }

    showVoiceQueryFallback(query) {
        alert(`Voice Query Detected: "${query}"\n\nPlease copy this text and paste it into the chat.`);
    }

    handleVoiceError(error) {
        let message = 'Voice search error occurred.';
        
        switch (error) {
            case 'no-speech':
                message = 'No speech detected. Please try again.';
                break;
            case 'audio-capture':
                message = 'Microphone not accessible. Please check permissions.';
                break;
            case 'not-allowed':
                message = 'Microphone access denied. Please allow microphone permissions.';
                break;
            case 'network':
                message = 'Network error. Please check your connection.';
                break;
            default:
                message = `Voice search error: ${error}`;
        }
        
        this.showErrorMessage(message);
    }

    showErrorMessage(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'voice-error-message';
        errorDiv.innerHTML = `
            <div class="voice-error-content">
                <i class="fas fa-exclamation-triangle"></i>
                <span>${message}</span>
                <button onclick="this.parentNode.parentNode.remove()" class="error-close">×</button>
            </div>
        `;
        
        // Add error styles
        if (!document.getElementById('voice-error-styles')) {
            const styles = `
                <style id="voice-error-styles">
                    .voice-error-message {
                        position: fixed;
                        top: 20px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: #f44336;
                        color: white;
                        padding: 12px 20px;
                        border-radius: 25px;
                        box-shadow: 0 4px 15px rgba(244, 67, 54, 0.3);
                        z-index: 10001;
                        animation: slideInTop 0.3s ease-out;
                    }
                    
                    .voice-error-content {
                        display: flex;
                        align-items: center;
                        gap: 8px;
                        font-weight: 600;
                        font-size: 14px;
                    }
                    
                    .error-close {
                        background: none;
                        border: none;
                        color: white;
                        font-size: 18px;
                        cursor: pointer;
                        margin-left: 8px;
                    }
                    
                    @keyframes slideInTop {
                        from { transform: translateX(-50%) translateY(-100%); opacity: 0; }
                        to { transform: translateX(-50%) translateY(0); opacity: 1; }
                    }
                </style>
            `;
            document.head.insertAdjacentHTML('beforeend', styles);
        }
        
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.remove();
            }
        }, 5000);
    }

    showUnsupportedMessage() {
        const container = document.querySelector('.voice-search-container');
        if (container) {
            container.innerHTML = `
                <div class="voice-unsupported">
                    <i class="fas fa-microphone-slash"></i>
                    Voice search is not supported in your browser. 
                    Please use Chrome, Firefox, or Safari for voice functionality.
                </div>
            `;
        }
    }
}

// Initialize voice search when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for other scripts to load
    setTimeout(() => {
        console.log('Initializing Voice Search...');
        window.voiceSearch = new VoiceSearch();
        
        // Add keyboard shortcuts for voice search
        document.addEventListener('keydown', function(event) {
            // Ctrl/Cmd + Shift + V to toggle voice search
            if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'V') {
                event.preventDefault();
                if (window.voiceSearch) {
                    window.voiceSearch.toggleVoiceSearch();
                }
            }
            
            // Alt + V for voice search (alternative shortcut)
            if (event.altKey && event.key === 'v') {
                event.preventDefault();
                if (window.voiceSearch) {
                    window.voiceSearch.toggleVoiceSearch();
                }
            }
        });
        
    }, 1000);
});

// Global functions for external access
window.toggleVoiceSearch = function() {
    if (window.voiceSearch) {
        window.voiceSearch.toggleVoiceSearch();
    }
};

window.setVoiceLanguage = function(lang) {
    if (window.voiceSearch && window.voiceSearch.recognition) {
        window.voiceSearch.recognition.lang = lang;
        console.log('Voice language set to:', lang);
    }
};