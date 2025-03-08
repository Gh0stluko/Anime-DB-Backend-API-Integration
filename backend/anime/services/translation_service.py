import logging
import requests
import time
import html
import os
from django.conf import settings

logger = logging.getLogger(__name__)

# Import lightweight translation libraries
try:
    import translators as ts
    import translators.server as tss
    TRANSLATORS_AVAILABLE = True
except ImportError:
    logger.warning("Translators package is not installed. Consider installing it for lightweight translation.")
    TRANSLATORS_AVAILABLE = False

class TranslationService:
    """Сервіс для перекладу текстів на українську мову"""

    @staticmethod
    def translate_text(text, source_lang='en', target_lang='uk'):
        """
        Перекладає текст на українську мову
        
        Args:
            text (str): Текст для перекладу
            source_lang (str): Мова оригіналу (по замовчуванню 'en')
            target_lang (str): Цільова мова (по замовчуванню 'uk')
            
        Returns:
            str: Перекладений текст або оригінал, якщо переклад не вдався
        """
        if not text:
            return ""
        
        # First try using Translators package (lightweight wrapper for various translation APIs)
        if TRANSLATORS_AVAILABLE:
            try:
                # Try multiple translation services with fallbacks
                # The correct method is tss.translate_text with provider parameter
                for engine in ['bing', 'google', 'reverso']:
                    try:
                        result = tss.translate_text(
                            query_text=text, 
                            translator=engine,
                            from_language=source_lang, 
                            to_language=target_lang
                        )
                        if result and result != text:
                            logger.info(f"Translation successful using {engine} engine")
                            return result
                    except Exception as e:
                        logger.debug(f"Failed to translate with {engine}: {str(e)}")
                        continue
                
                logger.info("All translators engines failed, trying direct API")
            except Exception as e:
                logger.warning(f"Failed to translate with translators package: {str(e)}")
        
        # Use free Google API as fallback
        try:
            return TranslationService._translate_with_free_google(text, source_lang, target_lang)
        except Exception as e:
            logger.error(f"All translation methods failed: {str(e)}")
            return text  # Повертаємо оригінал, якщо всі методи перекладу не вдалися
    
    @staticmethod
    def _translate_with_free_google(text, source_lang='en', target_lang='uk'):
        """Переклад за допомогою безкоштовного Google Translate API"""
        # Це неофіційний API, тому він може бути нестабільним
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': source_lang,
            'tl': target_lang,
            'dt': 't',
            'q': text
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # Розбір специфічної відповіді неофіційного API
        result = response.json()
        translated_text = ""
        
        # Обробка відповіді Google Translate
        for sentence in result[0]:
            if len(sentence) > 0:
                translated_text += sentence[0]
        
        return translated_text

    @staticmethod
    def detect_language(text):
        """
        Визначає мову тексту
        
        Args:
            text (str): Текст для аналізу
            
        Returns:
            str: Код мови (наприклад, 'en', 'ja', 'uk')
        """
        if not text:
            return 'en'  # Default to English for empty text
        
        # Try using translators package for language detection
        if TRANSLATORS_AVAILABLE:
            try:
                # Try language detection with correct method
                try:
                    # The correct method is tss.detect_language
                    for provider in ['google', 'bing']:
                        try:
                            result = tss.detect_language(
                                query_text=text[:100], 
                                translator=provider
                            )
                            if result:
                                return result
                        except Exception as e:
                            logger.debug(f"Language detection with {provider} failed: {str(e)}")
                            continue
                except Exception as e:
                    logger.debug(f"All detection methods failed: {str(e)}")
                    
                logger.info("All translators detection engines failed")
            except Exception as e:
                logger.warning(f"Translators language detection failed: {str(e)}")
                
        # Fallback to other methods
        return TranslationService._detect_language_fallback(text)
    
    @staticmethod
    def _detect_language_fallback(text):
        """
        Fallback method for language detection when other methods fail
        
        Args:
            text (str): Text to analyze
            
        Returns:
            str: Language code (e.g., 'en', 'ja', 'uk')
        """
        try:
            # Try using a free API for language detection
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                'client': 'gtx',
                'sl': 'auto',  # Auto-detect source language
                'tl': 'en',    # Target language doesn't matter here
                'dt': 't',
                'q': text[:100]  # Just use the first 100 chars to avoid request size limits
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # Parse response to get detected language
            result = response.json()
            # The detected language code should be in the third position
            if isinstance(result, list) and len(result) > 2:
                detected_lang = result[2]
                if isinstance(detected_lang, str) and detected_lang:
                    return detected_lang
            
            logger.warning(f"Unexpected response format from free Google Translate API: {result}")
            
        except Exception as e:
            logger.warning(f"Fallback language detection failed: {str(e)}")
            
        # If everything fails, check for common Japanese/Ukrainian characters
        # or just return English as default
        if any('\u3040' <= c <= '\u30ff' or '\u3400' <= c <= '\u4dbf' or '\u4e00' <= c <= '\u9fff' for c in text):
            return 'ja'  # Likely Japanese
        elif any('\u0400' <= c <= '\u04FF' for c in text):
            return 'uk'  # Likely Ukrainian/Russian
            
        return 'en'  # Default to English