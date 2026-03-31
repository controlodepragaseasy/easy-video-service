import asyncio
import base64
import io
from datetime import timedelta
from pathlib import Path

from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import edge_tts
import gunicorn

app = Flask(__name__)

# TTS Configuration
TTS_VOICE = "pt-PT-DuarteNeural"
TEMP_DIR = Path("/tmp/easy-video")
TEMP_DIR.mkdir(exist_ok=True)


async def _edge_tts_generate(text: str, output_path) -> None:
    """Generate audio using edge-tts (free, no API key needed)"""
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(str(output_path))


def _process_audio(audio_data=None, script_text=None):
    """
    Process audio: either from uploaded file or generate from text.
    Returns: duration in seconds
    """
    audio_path = TEMP_DIR / "generated_audio.mp3"
    
    if script_text:
        # Generate audio from text using edge-tts
        asyncio.run(_edge_tts_generate(script_text, audio_path))
        # Get duration (simplified - edge-tts doesn't return duration directly)
        # You may need to use moviepy or similar to get actual duration
        return 5.0  # Default duration, should be calculated from actual audio
    
    elif audio_data:
        # Save uploaded audio file
        audio_path.write_bytes(audio_data)
        # Calculate duration from audio file
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            duration = len(audio) / 1000.0  # Convert ms to seconds
            return duration
        except ImportError:
            # If pydub not available, return default duration
            return 10.0
    
    else:
        raise ValueError("Either audio_data or script_text must be provided")


def _create_video_frames(width=720, height=1280, duration=5.0, fps=30):
    """Create simple video frames from text"""
    frames = []
    num_frames = int(duration * fps)
    
    for i in range(num_frames):
        # Create a simple frame with background color
        frame = Image.new('RGB', (width, height), color=(20, 20, 20))
        # Could add text, images, effects here
        frames.append(frame)
    
    return frames


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200


@app.route('/create-video', methods=['POST'])
def create_video():
    """Create video from audio file or text script"""
    try:
        data = request.get_json() or {}
        audio_data = None
        script_text = data.get("script_text", "")
        
        # Get audio from file upload if provided
        if 'audio' in request.files:
            audio_file = request.files['audio']
            audio_data = audio_file.read()
        
        # Validate: need either audio or script
        if not audio_data and not script_text:
            return jsonify({
                "success": False,
                "error": "Either audio file or script_text is required"
            }), 400
        
        # Process audio (generate from text or use uploaded file)
        duration = _process_audio(audio_data=audio_data, script_text=script_text)
        
        # Create video frames
        frames = _create_video_frames(duration=duration)
        
        # Convert frames to base64 (first frame as preview)
        preview_buffer = io.BytesIO()
        frames[0].save(preview_buffer, format='PNG')
        preview_base64 = base64.b64encode(preview_buffer.getvalue()).decode()
        
        return jsonify({
            "success": True,
            "duration": duration,
            "frames_count": len(frames),
            "preview_image": preview_base64
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/generate-tts', methods=['POST'])
def generate_tts():
    """Generate text-to-speech audio using edge-tts"""
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        voice = data.get("voice", TTS_VOICE)
        
        if not text:
            return jsonify({
                "success": False,
                "error": "Text field is required"
            }), 400
        
        # Generate audio
        audio_path = TEMP_DIR / "tts_audio.mp3"
        asyncio.run(_edge_tts_generate(text, audio_path))
        
        # Read audio and encode to base64
        audio_bytes = audio_path.read_bytes()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        
        # Estimate duration (rough calculation: ~150 words per minute)
        word_count = len(text.split())
        estimated_duration = max(1.0, (word_count / 150) * 60)
        
        return jsonify({
            "success": True,
            "audio_base64": audio_base64,
            "duration": estimated_duration,
            "voice": voice
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)