# Video Production Service

## Purpose
The Video Production Service transforms text-based climate news articles into engaging short-form videos (9:16 format) optimized for TikTok, Instagram Reels, and YouTube Shorts. This service is critical for CliLens.AI's strategy to reach Gen-Z audiences where they consume content.

## Core Responsibilities
1. **Script Generation**: Convert article content into video-optimized scripts
2. **Voiceover Creation**: Text-to-speech generation with natural-sounding voices
3. **Visual Asset Management**: Source stock footage, images, and graphics
4. **Video Composition**: Automated video editing and rendering
5. **Platform Optimization**: Format videos for different social media platforms

## Architecture

### Components
- `main.py`: Main video production agent and entry point
- `__init__.py`: Service initialization

### Dependencies
- **Shared Modules**: `shared.config`, `shared.logger`, `shared.kafka_client`, `shared.database`
- **Video Generation**:
  - **Phase 2 (MVP)**: InVideo AI API for rapid deployment
  - **Phase 3 (Scale)**: Remotion + AWS Lambda for cost-effective rendering
- **Text-to-Speech**: ElevenLabs or OpenAI TTS
- **Asset Sources**: Pexels, Unsplash, or custom stock footage libraries

## Data Flow

```
Kafka (video_production_queue)
  → Article Content
  → Script Generation (LLM)
  → Voiceover Generation (TTS)
  → Visual Asset Selection
  → Video Composition
    ├→ Phase 2: InVideo API
    └→ Phase 3: Remotion + Lambda
  → Video Rendering
  → Storage (S3/CDN)
  → Kafka (videos_ready)
  → Publication
```

## Video Production Pipeline

### 1. Script Adaptation
Convert article text to video script:
- Break into 10-15 second segments
- Optimize for voiceover pacing
- Add visual cues and transitions
- Target 60-90 second total duration

**Example:**
```
Article: "Arctic sea ice decreased by 13% per decade since 1979..."

Script:
[0-10s] Hook: "Arctic ice is disappearing faster than ever."
[10-25s] Fact: "NASA data shows 13% decline per decade since 1979"
        Visual: Arctic ice satellite imagery
[25-40s] Context: "That's equivalent to losing an ice sheet the size of..."
        Visual: Comparison graphics
[40-60s] Impact: "What this means for global climate..."
        Visual: Infographics
```

### 2. Voiceover Generation
Text-to-speech with natural voices:
- Choose voice profile (gender, accent, tone)
- Generate audio segments
- Apply pacing and emphasis
- Background music integration

### 3. Visual Asset Sourcing
Automated asset selection:
- Query stock footage APIs (Pexels, Unsplash)
- Match keywords from script segments
- Climate-specific asset library
- Custom graphics and animations

### 4. Video Composition

#### Phase 2: InVideo API (MVP)
```python
# Quick deployment using InVideo API
invideo_client.create_video({
    "script": script_segments,
    "voiceover": audio_url,
    "style": "climate_news",
    "format": "9:16",
    "duration": 60
})
```

**Benefits:**
- Rapid deployment (days vs weeks)
- Minimal DevOps overhead
- Suitable for MVP validation
- ~$0.50-1.00 per video

**Limitations:**
- Higher cost at scale
- Less customization
- Dependency on third-party service

#### Phase 3: Remotion + Lambda (Scale)
```javascript
// Custom rendering with Remotion
const VideoComposition = () => (
  <Composition
    id="CliLensNews"
    component={ClimateNewsVideo}
    durationInFrames={1800} // 60s at 30fps
    fps={30}
    width={1080}
    height={1920}
  />
);
```

**Benefits:**
- Exponentially cheaper at scale (~$0.05 per video)
- Full brand control
- React-based templates (easy to modify)
- Parallel rendering via Lambda

**Architecture:**
```
Script → Remotion Template
       → Lambda Function Pool (10-100 concurrent)
       → Rendered Video Segments
       → S3 Storage
       → CloudFront CDN
```

### 5. Platform-Specific Optimization
- **TikTok**: 15-60s, vertical, fast-paced editing
- **Instagram Reels**: 15-90s, vertical, trending audio support
- **YouTube Shorts**: 15-60s, vertical, higher resolution
- **Twitter**: 60-90s, horizontal/vertical, auto-captions

## Kafka Integration

### Consumes From
- `video_production_queue`: Articles ready for video generation
- `scripts.generated`: Generated video scripts (future)

### Produces To
- `videos.render_jobs`: Rendering tasks for workers (Phase 3)
- `videos.completed`: Finished videos ready for publication
- `publication_queue`: Video publication triggers

## Configuration

### Phase 2 (InVideo)
- `video.invideo_api_key`: InVideo API key
- `video.invideo_api_url`: InVideo API endpoint
- `video.default_style`: Default video style template

### Phase 3 (Remotion + Lambda)
- `video.aws_region`: AWS region for Lambda
- `video.lambda_function_name`: Remotion renderer function
- `video.s3_bucket`: S3 bucket for rendered videos
- `video.cloudfront_domain`: CDN domain for delivery

### Common
- `video.target_duration_seconds`: Target video length (default: 60)
- `video.aspect_ratio`: Video aspect ratio (default: "9:16")
- `video.output_resolution`: Output resolution (default: "1080x1920")
- `tts.provider`: TTS provider (default: "elevenlabs")
- `tts.voice_id`: Default voice ID

## Database Schema

### Tables Used
- `video_scripts`: Generated video scripts
- `video_renders`: Rendering job tracking
- `video_assets`: Stock footage and graphics catalog
- `videos`: Final video metadata and URLs

## API Contract

### Input (Kafka Message)
```json
{
  "taskId": "task-20251022-001",
  "articleId": "uuid",
  "content": {
    "title": "Arctic Sea Ice Decline Accelerates",
    "summary": "NASA data shows...",
    "body": "Full article...",
    "factCheckElements": [...]
  },
  "videoParameters": {
    "duration": 60,
    "aspectRatio": "9:16",
    "platform": "tiktok",
    "voiceProfile": "professional-female"
  }
}
```

### Output (Kafka Message)
```json
{
  "taskId": "task-20251022-001",
  "articleId": "uuid",
  "videoId": "uuid",
  "videoUrl": "https://cdn.clilens.ai/videos/...",
  "thumbnailUrl": "https://cdn.clilens.ai/thumbnails/...",
  "metadata": {
    "duration": 62,
    "resolution": "1080x1920",
    "fileSize": 15728640,
    "format": "mp4",
    "renderTime": 45.2
  },
  "platforms": ["tiktok", "instagram", "youtube"],
  "status": "ready_for_publication"
}
```

## Running the Service

### Development (Phase 2)
```bash
cd src/backend/services/video_production_service
export INVIDEO_API_KEY=your_key
export ELEVENLABS_API_KEY=your_key
python src/main.py
```

### Development (Phase 3)
```bash
# Deploy Remotion renderer to Lambda
cd remotion-renderer
npm run deploy

# Run video production service
export AWS_REGION=us-east-1
export LAMBDA_FUNCTION_NAME=remotion-renderer
python src/main.py
```

### Docker
```bash
docker build -t clilens-video-production-service .
docker run \
  -e INVIDEO_API_KEY=your_key \
  -e ELEVENLABS_API_KEY=your_key \
  clilens-video-production-service
```

## Testing
```bash
pytest tests/test_video_production.py
```

## Logging
Structured logging with video production context:
- `task_id`: Task identifier
- `video_id`: Video UUID
- `render_status`: Current rendering status
- `render_time_seconds`: Time to render video
- `asset_count`: Number of visual assets used

## Error Handling
- **TTS Failures**: Retry with alternative voice or provider
- **Asset Availability**: Fallback to generic climate visuals
- **Rendering Timeouts**: Cancel and retry with simpler template
- **Storage Failures**: Retry S3 upload with exponential backoff

## Performance Metrics

### Phase 2 (InVideo)
- Render time: 2-5 minutes per video
- Cost: $0.50-1.00 per video
- Throughput: ~10-20 videos/hour

### Phase 3 (Remotion + Lambda)
- Render time: 30-90 seconds per video
- Cost: $0.03-0.05 per video
- Throughput: 100+ videos/hour (parallelized)

## Future Enhancements
- AI avatar/presenter integration (Synthesia, HeyGen)
- Real-time video generation (live news updates)
- Interactive video elements (polls, quizzes)
- Multi-language dubbing
- Auto-generated captions and subtitles
- Advanced motion graphics and animations
- Brand-specific visual templates
- A/B testing for video styles
