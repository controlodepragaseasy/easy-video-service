import base64
import io
from pathlib import Path

from flask import Flask, request, jsonify
from PIL import Image
from gtts import gTTS
# TTS: gtts (sem API key) - redeployed

app = Flask(__name__)

TEMP_DIR = Path("/tmp/easy-video")
TEMP_DIR.mkdir(exist_ok=True)


def _gtts_generate(text, output_path):
    """Generate audio using gTTS (free, no API key needed)"""
    tts = gTTS(text=text, lang='pt', tld='pt')
    tts.save(str(output_path))


def _process_audio(audio_data=None, script_text=None):
    """Process audio: generate from text or use uploaded file."""
    audio_path = TEMP_DIR / "generated_audio.mp3"
    if script_text:
        _gtts_generate(script_text, audio_path)
        word_count = len(script_text.split())
        duration = max(5.0, (word_count / 150) * 60)
        return duration
    elif audio_data:
        audio_path.write_bytes(audio_data)
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except ImportError:
            return 10.0
    else:
        raise ValueError("Either audio_data or script_text must be provided")


def _create_video_frames(width=720, height=1280, duration=5.0, fps=30):
    """Create simple video frames."""
    frames = []
    num_frames = int(duration * fps)
    for i in range(num_frames):
        frame = Image.new("RGB", (width, height), color=(20, 20, 20))
        frames.append(frame)
    return frames


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/create-video", methods=["POST"])
def create_video():
    """Create video from audio file or text script."""
    try:
        data = request.get_json() or {}
        audio_data = None
        script_text = data.get("script_text", "")
        if "audio" in request.files:
            audio_data = request.files["audio"].read()
        if not audio_data and not script_text:
            return jsonify({
                "success": False,
                "error": "Either audio file or script_text is required"
            }), 400
        duration = _process_audio(audio_data=audio_data, script_text=script_text)
        frames = _create_video_frames(duration=duration)
        preview_buffer = io.BytesIN()
        frames[0].save(preview_buffer, format="PNG")
        preview_base64 = base64.b64encode(preview_buffer.getvalue()).decode()
        return jsonify({
            "success": True,
            "duration": duration,
            "frames_count": len(frames),
            "preview_image": preview_base64
        }), 200
    except Exception as e:
        return vsonify({"success": False, "error": str(e)}), 500


@app.route("/generate-tts", methods=["POST"])
def generate_tts():
    """Generate TTS audio using gTTS."""
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"success": False, "error": "Text field is required"}), 400
        audio_path = TEMP_DIR / "tts_audio.mp3"
        _gtts_generate(text, audio_path)
        audio_bytes = audio_path.read_bytes()
        audio_base64 = base64.b64encode(audio_bytes).decode()
        word_count = len(text.split())
        estimated_duration = max(1.0, (word_count / 150) * 60)
        return jsonify({
            "success": True,
            "audio_base64": audio_base64,
            "duration": estimated_duration,
            "voice": "pt-PT (gTTS)"
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def generate_tts_with_voice(text, voice='pt-BR-AntonioNeural'):
        """Gera áudio com voz configurável (PT-BR por defeito para UFC)"""
        try:
                    output_path = f"{OUTPUT_DIR}/naracao_{datetime.utcnow().timestamp()}.mp3"
                    import edge_tts
                    import asyncio
            
            async def get_tts():
                            communicate = edge_tts.Communicate(text, voice=voice, rate="+10%", pitch="+0Hz")
                            await communicate.save(output_path)
                
        asyncio.run(get_tts())
        return output_path
except Exception as e:
        logger.error(f"Erro TTS: {str(e)}")
        raise


def create_sports_text_frame(text, position='top'):
        """Cria frame de texto estilo UFC - barra vermelha, texto branco bold"""
    try:
                width, height = 1080, 1920
                image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
        
        bar_height = 130
        bar_y = 60 if position == 'top' else height - 190

        draw.rectangle([(0, bar_y), (width, bar_y + bar_height)], fill=(180, 0, 0, 230))

        try:
                        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
                        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
                    except:
                                    font_large = ImageFont.load_default()
                                    font_small = font_large
                        
        max_chars = 32
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
                        test = (current_line + " " + word).strip()
                        if len(test) <= max_chars:
                                            current_line = test
                        else:
                                            if current_line:
                                                                    lines.append(current_line)
                                                                current_line = word
                                    if current_line:
                                                    lines.append(current_line)
                                        
        font = font_large if len(lines) == 1 else font_small
        line_height = 48
        total_h = len(lines) * line_height
        text_y = bar_y + (bar_height - total_h) // 2

        for line in lines:
                        bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            tx = (width - tw) // 2
            draw.text((tx + 2, text_y + 2), line, fill=(0, 0, 0, 200), font=font)
            draw.text((tx, text_y), line, fill=(255, 255, 255, 255), font=font)
            text_y += line_height

        output_path = f"{OUTPUT_DIR}/sports_frame_{position}_{datetime.utcnow().timestamp()}.png"
        image.save(output_path)
        return output_path
except Exception as e:
        logger.error(f"Erro frame sports: {str(e)}")
        raise


def compose_sports_video(video_path, audio_path, hook_frame, cta_frame):
        """Compõe vídeo UFC 9:16 com FFmpeg - duração do áudio, máx 60s"""
    try:
                output_path = f"{OUTPUT_DIR}/ufc_short_{int(datetime.utcnow().timestamp())}.mp4"

        dur_cmd = [
                        'ffprobe', '-v', 'error',
                        '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        audio_path
        ]
        result = subprocess.run(dur_cmd, capture_output=True, text=True)
        try:
                        duration = min(float(result.stdout.strip()) + 1.0, 60.0)
        except:
            duration = 58.0

        cmd = [
                        'ffmpeg',
                        '-stream_loop', '-1', '-i', video_path,
                        '-i', audio_path,
                        '-i', hook_frame,
                        '-i', cta_frame,
                        '-filter_complex',
                        '[0:v]scale=1080:1920:force_original_aspect_ratio=increase,'
                        'crop=1080:1920,setsar=1[bg];'
                        '[bg][2:v]overlay=0:0[v1];'
                        '[v1][3:v]overlay=0:main_h-overlay_h[vout]',
                        '-map', '[vout]',
                        '-map', '1:a',
                        '-c:v', 'libx264',
                        '-preset', 'fast',
                        '-c:a', 'aac',
                        '-b:a', '128k',
                        '-r', '30',
                        '-t', str(duration),
                        '-shortest',
                        '-y',
                        output_path
        ]

        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
except Exception as e:
        logger.error(f"Erro FFmpeg sports: {str(e)}")
        raise


@app.route('/create-sports-video', methods=['POST'])
def create_sports_video():
        """
            Cria Short UFC/MMA vertical 9:16 narrado em PT-BR.
                Body JSON: script_text, hook, cta, pexels_query, voice (opcional)
                    Retorna: ficheiro MP4
                        """
    try:
                data = request.get_json()

        required_fields = ['script_text', 'hook', 'cta', 'pexels_query']
        missing = [f for f in required_fields if f not in data]
        if missing:
                        return jsonify({'error': f'Missing fields: {missing}'}), 400

        voice = data.get('voice', 'pt-BR-AntonioNeural')

        logger.info(f"[UFC] Gerando video - hook: {data['hook'][:60]}")

        audio_path = generate_tts_with_voice(data['script_text'], voice)
        video_stock = download_pexels_video(data['pexels_query'])
        hook_frame = create_sports_text_frame(data['hook'], position='top')
        cta_frame = create_sports_text_frame(data['cta'], position='bottom')
        output_path = compose_sports_video(video_stock, audio_path, hook_frame, cta_frame)

        logger.info(f"[UFC] Video criado: {output_path}")

        return send_file(
                        output_path,
                        mimetype='video/mp4',
                        as_attachment=True,
                        download_name=f'ufc_short_{int(datetime.utcnow().timestamp())}.mp4'
        )

except Exception as e:
        logger.error(f"[UFC] Erro: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
