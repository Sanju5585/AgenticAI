"""
🌍 Advanced AI-powered multilingual support utilities for the e-commerce assistant.
Handles intelligent translation, language detection, and multilingual query processing with AI enhancement.
"""

TRANSLATION_AVAILABLE = False
try:
    from deep_translator import GoogleTranslator
    from langdetect import detect, LangDetectException
    import ssl
    import urllib3
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    TRANSLATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Translation libraries not available ({e}). Install deep-translator and langdetect for multilingual support.")
    GoogleTranslator = None
    detect = None
    LangDetectException = Exception
    ssl = None
    urllib3 = None
    requests = None

import re
from typing import Dict, Tuple, Optional, List

class MultilingualProcessor:
    """🤖 AI-driven multilingual query processing and translation with enhanced intelligence"""
    
    def __init__(self):
        if TRANSLATION_AVAILABLE:
            try:
                # Initialize the deep-translator with Google service
                self.translator = GoogleTranslator(source='auto', target='en')
                print("🌍 AI Multilingual Processor initialized successfully with deep-translator")
                
            except Exception as e:
                print(f"⚠️  Translator initialization error: {e}")
                self.translator = None
        else:
            self.translator = None
    
    def detect_language(self, text: str) -> str:
        """🧠 AI-enhanced language detection with context awareness"""
        if not TRANSLATION_AVAILABLE:
            return 'en'  # Default to English
            
        try:
            # Enhanced detection with preprocessing
            cleaned_text = self._preprocess_for_detection(text)
            detected = detect(cleaned_text)
            
            # AI-powered validation of detection
            validated_lang = self._validate_language_detection(text, detected)
            
            print(f"🌍 Language detected: {validated_lang} (from: '{text[:30]}...')")
            return validated_lang
            
        except (LangDetectException, Exception) as e:
            print(f"⚠️  Language detection failed: {e}")
            return 'en'  # Default to English if detection fails
    
    def translate_to_english(self, text: str, source_lang: str = None) -> Tuple[str, str]:
        """
        🤖 AI-enhanced translation to English with context preservation and intelligent fallbacks
        Returns: (translated_text, detected_language)
        """
        if not TRANSLATION_AVAILABLE:
            return text, 'en'
        
        try:
            # Detect language if not provided
            if source_lang is None:
                source_lang = self.detect_language(text)
            
            # If already English, return as-is
            if source_lang == 'en':
                return text, source_lang
            
            print(f"🔄 Translating from {source_lang}: '{text}'")
            
            # AI-enhanced translation with deep-translator
            translated_text = self._execute_ai_translation(text, source_lang)
            
            # Post-process for e-commerce context
            enhanced_translation = self._enhance_translation_for_ecommerce(
                translated_text, text, source_lang
            )
            
            print(f"✅ AI Translation: '{text}' → '{enhanced_translation}'")
            return enhanced_translation, source_lang
            
        except Exception as e:
            print(f"❌ Translation error: {e}")
            return text, source_lang or 'unknown'
    
    def _preprocess_for_detection(self, text: str) -> str:
        """Preprocess text for better language detection"""
        # Remove excessive punctuation and numbers that can confuse detection
        cleaned = re.sub(r'[^\w\s]', ' ', text)
        cleaned = re.sub(r'\d+', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else text
    
    def _validate_language_detection(self, text: str, detected_lang: str) -> str:
        """AI-powered validation of language detection results"""
        # Use AI to detect language more accurately for common e-commerce languages
        try:
            # First try AI-based validation
            validation_prompt = f"""
            Detect the language of this text: "{text}"
            
            Return only the ISO 639-1 language code (2 letters) from these options:
            hi (Hindi), es (Spanish), fr (French), de (German), zh (Chinese), 
            ja (Japanese), ko (Korean), ar (Arabic), en (English), mr (Marathi),
            ta (Tamil), te (Telugu), bn (Bengali), pt (Portuguese), it (Italian)
            
            If you're not sure, return the closest match.
            
            Language code:
            """
            
            from ecom_llm import google_generative_ai_llm
            response = google_generative_ai_llm.invoke(validation_prompt)
            ai_detected = response.content.strip().lower()
            
            # Validate AI response
            valid_codes = ['hi', 'es', 'fr', 'de', 'zh', 'ja', 'ko', 'ar', 'en', 'mr', 'ta', 'te', 'bn', 'pt', 'it']
            if ai_detected in valid_codes:
                if ai_detected != detected_lang:
                    print(f"🔄 AI corrected language detection from {detected_lang} to {ai_detected}")
                return ai_detected
            
        except Exception as e:
            print(f"AI language validation failed: {e}")
        
        # Fallback to basic character analysis
        # Check for common script patterns
        if any('\u0900' <= char <= '\u097F' for char in text):  # Devanagari script
            if detected_lang in ['mr', 'ne', 'sa']:  # Could be Marathi, Nepali, Sanskrit
                return detected_lang
            return 'hi'  # Default to Hindi for Devanagari
        elif any('\u0980' <= char <= '\u09FF' for char in text):  # Bengali script
            return 'bn'
        elif any('\u0B80' <= char <= '\u0BFF' for char in text):  # Tamil script
            return 'ta'
        elif any('\u0C00' <= char <= '\u0C7F' for char in text):  # Telugu script
            return 'te'
        
        return detected_lang
    
    def _execute_ai_translation(self, text: str, source_lang: str) -> str:
        """Execute AI-enhanced translation with fallback strategies using deep-translator"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Primary translation attempt with deep-translator
                if self.translator:
                    # Update the source language for this translation
                    self.translator.source = source_lang
                    self.translator.target = 'en'
                    
                    translated_text = self.translator.translate(text)
                    
                    if translated_text and self._is_valid_translation(translated_text, text):
                        return translated_text.strip()
                
            except Exception as api_error:
                print(f"⚠️  Translation attempt {attempt + 1} failed: {api_error}")
                if attempt < max_retries - 1:
                    continue
                else:
                    # Final fallback: AI-based translation
                    print("🤖 Falling back to AI-powered translation...")
                    ai_translation = self._ai_powered_translation(text, source_lang)
                    return ai_translation if ai_translation else text
        
        return text
    
    def _is_valid_translation(self, translated: str, original: str) -> bool:
        """Validate translation quality"""
        # Basic quality checks
        if not translated or len(translated.strip()) == 0:
            return False
        
        # Check if translation is too similar to original (might be unchanged)
        if translated.lower().strip() == original.lower().strip():
            return False
        
        # Check for obvious translation artifacts
        artifacts = ['translated by', 'translation error', 'google translate']
        if any(artifact in translated.lower() for artifact in artifacts):
            return False
        
        return True
    
    def _ai_powered_translation(self, text: str, source_lang: str) -> Optional[str]:
        """AI-powered translation fallback using LLM"""
        try:
            from ecom_llm import google_generative_ai_llm
            
            # Language name mapping
            lang_names = {
                'hi': 'Hindi',
                'es': 'Spanish', 
                'fr': 'French',
                'de': 'German',
                'zh': 'Chinese',
                'ja': 'Japanese',
                'ko': 'Korean',
                'ar': 'Arabic',
                'mr': 'Marathi',
                'ta': 'Tamil',
                'te': 'Telugu',
                'bn': 'Bengali'
            }
            
            lang_name = lang_names.get(source_lang, f'language code {source_lang}')
            
            # Create focused e-commerce translation prompt
            prompt = f"""
            Translate this {lang_name} e-commerce query to English. Focus on the main product or shopping intent being requested.
            
            Translation guidelines for e-commerce:
            - Identify the main product category (clothing, shoes, accessories, electronics, etc.)
            - Preserve price/budget information if mentioned
            - Convert to clear, searchable English terms
            - Remove unnecessary filler words
            - Focus on the core shopping intent
            
            Original query: "{text}"
            
            Provide ONLY the English translation (no explanations):
            """
            
            response = google_generative_ai_llm.invoke(prompt)
            ai_translation = response.content.strip()
            
            # Clean up AI response
            if ai_translation.startswith('"') and ai_translation.endswith('"'):
                ai_translation = ai_translation[1:-1]
            
            print(f"🤖 AI Translation: '{ai_translation}'")
            return ai_translation
            
        except Exception as e:
            print(f"❌ AI translation failed: {e}")
            return None
    
    def _enhance_translation_for_ecommerce(self, translated: str, original: str, source_lang: str) -> str:
        """AI-driven enhancement of translation for e-commerce context"""
        # E-commerce specific improvements
        enhanced = translated.lower().strip()
        
        # Remove common unnecessary phrases that appear in translations
        common_removals = [
            'show me some', 'give me some', 'i want some', 'i need some',
            'please show', 'can you show', 'let me see', 'i would like',
            'could you', 'please give', 'i am looking for'
        ]
        
        for removal in common_removals:
            if removal in enhanced:
                enhanced = enhanced.replace(removal, '').strip()
        
        # Remove excessive stop words for cleaner search
        stop_words = ['some', 'any', 'please', 'can', 'you', 'show', 'me', 'give', 'i', 'want', 'need', 'would', 'like', 'could', 'am', 'looking', 'for']
        words = enhanced.split()
        cleaned_words = [word for word in words if word not in stop_words and len(word) > 1]
        
        if cleaned_words:
            enhanced = ' '.join(cleaned_words)
        
        # Ensure we return something meaningful
        return enhanced if enhanced else translated
    
    def process_multilingual_query(self, query: str) -> Dict[str, str]:
        """
        🧠 AI-powered processing of multilingual queries with enhanced intelligence
        Returns dict with: original_query, translated_query, detected_language, processing_notes, confidence
        """
        result = {
            'original_query': query,
            'translated_query': query,
            'detected_language': 'en',
            'processing_notes': [],
            'confidence': 'high'
        }
        
        if not TRANSLATION_AVAILABLE:
            result['processing_notes'].append('Translation not available - using original query')
            result['confidence'] = 'low'
            return result
        
        # AI-enhanced language detection
        detected_lang = self.detect_language(query)
        result['detected_language'] = detected_lang
        
        # AI-powered translation if needed
        if detected_lang != 'en':
            translated_query, confirmed_lang = self.translate_to_english(query, detected_lang)
            result['translated_query'] = translated_query
            result['detected_language'] = confirmed_lang
            result['processing_notes'].append(f'AI-translated from {confirmed_lang} to English')
            
            # Assess translation confidence
            if len(translated_query.split()) >= len(query.split()) * 0.5:
                result['confidence'] = 'high'
            else:
                result['confidence'] = 'medium'
        else:
            result['processing_notes'].append('Query detected as English - no translation needed')
        
        return result

# Global enhanced instance
multilingual_processor = MultilingualProcessor()

# Enhanced convenience functions
def detect_and_translate(query: str) -> Tuple[str, str]:
    """
    🚀 Enhanced convenience function to detect and translate query
    Returns: (translated_query, detected_language)
    """
    result = multilingual_processor.process_multilingual_query(query)
    return result['translated_query'], result['detected_language']

def is_multilingual_available() -> bool:
    """Check if multilingual processing is available"""
    return TRANSLATION_AVAILABLE

def get_supported_languages() -> List[str]:
    """Get list of supported language codes"""
    return ['en', 'hi', 'es', 'fr', 'de', 'zh', 'ja', 'ko', 'ar', 'pt', 'it', 'ru']

def get_language_name(lang_code: str) -> str:
    """Get human-readable language name from code"""
    lang_names = {
        'en': 'English',
        'hi': 'Hindi (हिंदी)',
        'es': 'Spanish (Español)', 
        'fr': 'French (Français)',
        'de': 'German (Deutsch)',
        'zh': 'Chinese (中文)',
        'ja': 'Japanese (日本語)',
        'ko': 'Korean (한국어)',
        'ar': 'Arabic (العربية)',
        'pt': 'Portuguese (Português)',
        'it': 'Italian (Italiano)',
        'ru': 'Russian (Русский)'
    }
    return lang_names.get(lang_code, f'Unknown ({lang_code})')