import fitz  # PyMuPDF for PDF operations
from langdetect import detect  # Language detection
from googletrans import Translator  # Google Translate API
import re  # Regular expressions for text parsing

# Function to extract text from a PDF file
def extract_text_from_pdf(path):
    try:
        doc = fitz.open(path)
        text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text().replace("\n"," ")
            text += page_text + "\n"
        return text  
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None
    
def format_text(text):
    lines = text.split("\n")
    formatted_lines=[]

    for line in lines:
        # Remove excessive whitespaces
        cleaned_line = ' '.join(line.split())
        # when finds the dot it automatically moves the dot in the next
        #cleaned_line = cleaned_line.replace("•", "\n•")

        # Add a newline after the amount for each food
        formatted_line = re.sub(r'(\d+)\s+(gr\)|g \)|gr|g|unità)', r'\1 \2\n', cleaned_line)

        if not formatted_line.startswith("•"):
            formatted_lines.append(formatted_line.strip())

    # Join formatted lines back into a single string
    formatted_text = '\n'.join(formatted_lines)
    return formatted_text

# Function to detect the language of a text
def detect_language(text):
    try:
        lang = detect(text)
        return lang
    except Exception as e:
        print(f"Error detecting language: {e}")
        return None

# Function to translate text in segments to handle large text blocks
def translate_text_segments(text, src_language, target_language, segment_length=1000):
    translator = Translator()
    translated_text = ""
    segments = [text[i:i + segment_length] for i in range(0, len(text), segment_length)]

    for segment in segments:
        try:
            translation = translator.translate(segment, src=src_language, dest=target_language)
            translated_text += translation.text + " "
        except Exception as e:
            print(f"Error translating segment: {e}")
            translated_text += segment + " "  # Fallback to original segment if translation fails

    return translated_text


# Define path to the PDF file
path = r"C:\Users\Raf\Desktop\DietShopper\app\pdf files\Aurora schema.pdf"

extracted_text = extract_text_from_pdf(path)
formatted_text = format_text(extracted_text)

print(formatted_text)


