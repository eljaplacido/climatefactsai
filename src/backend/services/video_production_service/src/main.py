"""
Video Production Agent - Main Entry Point

Vastaa:
- Text-to-speech generaatio
- Stock-median haku
- Videoeditointi ja renderöinti
- 9:16 short-form videoiden tuotanto
"""

import os
import json
from typing import Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

import sys
from kafka import KafkaConsumer

# Add src/backend to path for shared module imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from shared.kafka_client import KafkaClient
from shared.database import PostgresClient
from shared.logger import setup_logger


class VideoProductionAgent:
    """
    Video Production Agent

    Luo lyhyitä uutisvideoita (9:16 TikTok/Instagram Reels -formaatti)
    tekstiyhteenvedoista.
    """

    def __init__(self):
        """Alusta Video Production Agent"""
        # Logger
        self.logger = setup_logger("video_production")

        # Kafka
        self.kafka = KafkaClient()

        # PostgreSQL
        self.postgres = PostgresClient()

        # Asetukset
        self.video_output_dir = Path(os.getenv("VIDEO_OUTPUT_DIR", "./output/videos"))
        self.video_output_dir.mkdir(parents=True, exist_ok=True)

        # TTS (Text-to-Speech) configuration
        self.tts_provider = os.getenv("TTS_PROVIDER", "openai")  # openai, elevenlabs, azure
        self.tts_voice = os.getenv("TTS_VOICE", "alloy")

        # Video settings
        self.default_aspect_ratio = "9:16"  # TikTok/Reels format
        self.default_max_duration = 90  # 90 seconds
        self.default_fps = 30

        self.logger.info(
            "VideoProductionAgent initialized",
            output_dir=str(self.video_output_dir),
            tts_provider=self.tts_provider
        )

    def run(self):
        """Käynnistä agentti"""
        self.logger.info("Starting Video Production Agent")

        # Kuuntele video_queue:ta
        consumer = KafkaConsumer(
            self.kafka.settings.kafka_topic_video_queue,
            bootstrap_servers=self.kafka.settings.kafka_bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id="video_production_group",
            auto_offset_reset='earliest'
        )

        self.logger.info(
            "Listening for video production tasks",
            topic=self.kafka.settings.kafka_topic_video_queue
        )

        try:
            for message in consumer:
                task = message.value
                self._process_video_task(task)
        except KeyboardInterrupt:
            self.logger.info("Shutting down Video Production Agent")
        finally:
            consumer.close()
            self.kafka.close()
            self.postgres.close()

    def _process_video_task(self, task: Dict[str, Any]):
        """
        Käsittele videontuottotehtävä

        Args:
            task: Video production -tehtävä
        """
        task_id = task.get("taskId")
        command = task.get("command")

        self.logger.info(
            "Processing video production task",
            task_id=task_id,
            command=command
        )

        try:
            if command == "produce_video":
                self._produce_video(
                    task_id=task_id,
                    summary_text=task.get("summaryText", ""),
                    parameters=task.get("parameters", {})
                )
            else:
                self.logger.warning(
                    "Unknown command",
                    task_id=task_id,
                    command=command
                )

        except Exception as e:
            self.logger.error(
                "Failed to process video task",
                task_id=task_id,
                error=str(e),
                exc_info=True
            )

    def _produce_video(
        self,
        task_id: str,
        summary_text: str,
        parameters: Dict[str, Any]
    ):
        """
        Tuota video yhteenvedosta

        Args:
            task_id: Tehtävätunniste
            summary_text: Yhteenveto teksti
            parameters: Videoparametrit (aspectRatio, maxDurationSeconds, style)
        """
        self.logger.info(
            "Producing video",
            task_id=task_id,
            text_length=len(summary_text)
        )

        start_time = datetime.now(timezone.utc)

        # 1. Valmistele skripti (jaa osiin jos liian pitkä)
        script_segments = self._prepare_script(summary_text, parameters)

        # 2. Generoi TTS-ääni
        audio_path = self._generate_tts(
            task_id=task_id,
            script_segments=script_segments
        )

        # 3. Hae stock-mediaa (kuvat/videot)
        media_assets = self._fetch_stock_media(
            task_id=task_id,
            script_segments=script_segments
        )

        # 4. Renderöi video
        video_path = self._render_video(
            task_id=task_id,
            audio_path=audio_path,
            media_assets=media_assets,
            script_segments=script_segments,
            parameters=parameters
        )

        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()

        # 5. Tallenna metadata tietokantaan
        self._save_video_metadata(
            task_id=task_id,
            video_path=video_path,
            processing_time_ms=processing_time * 1000
        )

        # 6. Julkaise valmis video -ilmoitus
        self._publish_video_ready(task_id, video_path)

        self.logger.info(
            "Video production completed",
            task_id=task_id,
            video_path=video_path,
            processing_time_seconds=processing_time
        )

    def _prepare_script(
        self,
        summary_text: str,
        parameters: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Valmistele video-skripti

        Args:
            summary_text: Yhteenveto
            parameters: Parametrit

        Returns:
            Lista skripti-segmenttejä
        """
        # Yksinkertainen toteutus: jaa lauseisiin
        # Tuotannossa käytettäisiin LLM:ää optimoimaan skripti

        sentences = summary_text.split('. ')
        segments = []

        for i, sentence in enumerate(sentences):
            if sentence.strip():
                segments.append({
                    "index": i,
                    "text": sentence.strip() + ".",
                    "duration_estimate": len(sentence) / 15  # ~15 chars per second
                })

        return segments

    def _generate_tts(
        self,
        task_id: str,
        script_segments: List[Dict[str, str]]
    ) -> str:
        """
        Generoi TTS-äänitiedosto

        Args:
            task_id: Tehtävätunniste
            script_segments: Skriptisegmentit

        Returns:
            Polku äänitiedostoon
        """
        self.logger.info(
            "Generating TTS audio",
            task_id=task_id,
            segment_count=len(script_segments)
        )

        # Yhdistä kaikki segmentit yhteen tekstiin
        full_text = " ".join([seg["text"] for seg in script_segments])

        # Käytä OpenAI TTS API:a (jos käytettävissä)
        # Tämä on placeholder - todellinen toteutus käyttäisi OpenAI API:a
        audio_filename = f"tts_{task_id}.mp3"
        audio_path = self.video_output_dir / audio_filename

        # PLACEHOLDER: Todellisessa toteutuksessa:
        # from openai import OpenAI
        # client = OpenAI()
        # response = client.audio.speech.create(
        #     model="tts-1",
        #     voice=self.tts_voice,
        #     input=full_text
        # )
        # response.stream_to_file(audio_path)

        # Nyt luodaan vain tyhjä tiedosto
        audio_path.touch()

        self.logger.info(
            "TTS audio generated (placeholder)",
            task_id=task_id,
            audio_path=str(audio_path)
        )

        return str(audio_path)

    def _fetch_stock_media(
        self,
        task_id: str,
        script_segments: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Hae stock-mediaa (kuvat/videot)

        Args:
            task_id: Tehtävätunniste
            script_segments: Skriptisegmentit

        Returns:
            Lista media-assetteja
        """
        self.logger.info(
            "Fetching stock media",
            task_id=task_id
        )

        # PLACEHOLDER: Todellisessa toteutuksessa käytettäisiin:
        # - Pexels API
        # - Unsplash API
        # - Pixabay API

        media_assets = []
        for seg in script_segments:
            media_assets.append({
                "segment_index": seg["index"],
                "type": "image",  # or "video"
                "url": "https://placeholder.com/climate-news.jpg",
                "duration": seg.get("duration_estimate", 3.0)
            })

        return media_assets

    def _render_video(
        self,
        task_id: str,
        audio_path: str,
        media_assets: List[Dict[str, str]],
        script_segments: List[Dict[str, str]],
        parameters: Dict[str, Any]
    ) -> str:
        """
        Renderöi lopullinen video

        Args:
            task_id: Tehtävätunniste
            audio_path: Polku äänitiedostoon
            media_assets: Media-assetit
            script_segments: Skriptisegmentit
            parameters: Videoparametrit

        Returns:
            Polku videotiedostoon
        """
        self.logger.info(
            "Rendering video",
            task_id=task_id,
            media_count=len(media_assets)
        )

        # PLACEHOLDER: Todellisessa toteutuksessa käytettäisiin:
        # - moviepy (Python video editing library)
        # - ffmpeg (command-line video processing)

        # Esimerkki moviepy:lla:
        # from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
        # clips = []
        # for asset in media_assets:
        #     clip = VideoFileClip(asset["url"]).set_duration(asset["duration"])
        #     clips.append(clip)
        # final_video = concatenate_videoclips(clips)
        # final_video.audio = AudioFileClip(audio_path)
        # final_video.write_videofile(output_path, fps=30)

        video_filename = f"video_{task_id}.mp4"
        video_path = self.video_output_dir / video_filename

        # Luo placeholder-tiedosto
        video_path.touch()

        self.logger.info(
            "Video rendered (placeholder)",
            task_id=task_id,
            video_path=str(video_path)
        )

        return str(video_path)

    def _save_video_metadata(
        self,
        task_id: str,
        video_path: str,
        processing_time_ms: float
    ):
        """
        Tallenna videon metadata tietokantaan

        Args:
            task_id: Tehtävätunniste
            video_path: Polku videoon
            processing_time_ms: Prosessointiaika millisekunteina
        """
        query = """
        INSERT INTO videos (
            task_id, video_path, processing_time_ms, created_at
        ) VALUES (
            :task_id, :video_path, :processing_time_ms, :created_at
        )
        """

        self.postgres.execute_update(
            query,
            params={
                "task_id": task_id,
                "video_path": video_path,
                "processing_time_ms": processing_time_ms,
                "created_at": datetime.now(timezone.utc)
            }
        )

        self.logger.info(
            "Video metadata saved to database",
            task_id=task_id
        )

    def _publish_video_ready(self, task_id: str, video_path: str):
        """
        Julkaise video valmis -ilmoitus

        Args:
            task_id: Tehtävätunniste
            video_path: Polku videoon
        """
        message = {
            "event": "video_ready",
            "taskId": task_id,
            "videoPath": video_path,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        self.kafka.produce(
            topic=self.kafka.settings.kafka_topic_orchestrator_responses,
            payload=message,
            key=task_id
        )

        self.logger.info(
            "Video ready notification published",
            task_id=task_id
        )


def main():
    """Main entry point"""
    agent = VideoProductionAgent()
    agent.run()


if __name__ == "__main__":
    main()
