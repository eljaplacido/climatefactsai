# Orchestration Service

## Purpose
The Orchestration Service acts as the central coordinator for the entire CliLens.AI workflow. It manages task lifecycle, coordinates communication between worker agents, and ensures workflow integrity.

## Core Responsibilities
1. **Workflow Management**: Initiate and coordinate multi-stage content processing workflows
2. **Task Lifecycle**: Create, track, and manage task states from initiation to publication
3. **Agent Coordination**: Delegate work to specialized worker agents via Kafka
4. **State Management**: Maintain workflow state in Redis for resilience
5. **Error Handling**: Retry failed stages and handle error scenarios
6. **HITL Integration**: Trigger human-in-the-loop review when required

## Architecture

### Components
- `main.py`: Main orchestrator agent and entry point
- `workflow.py`: Workflow orchestration logic and stage delegation
- `state_machine.py`: State machine for workflow and stage status management

### Dependencies
- **Shared Modules**: `shared.config`, `shared.logger`, `shared.kafka_client`, `shared.database`
- **State Store**: Redis for workflow state persistence
- **Database**: PostgreSQL for task history and metadata

## Workflow Stages

```
START
  → Content Discovery (Ingestion Service)
  → Fact Checking (Verification Service)
  → Content Creation (Content Creation Service)
  → HITL Review (Human Review)
  → Publication
  → END
```

## State Machine

### Workflow States
- `PENDING`: Workflow created but not started
- `RUNNING`: Workflow in progress
- `PAUSED`: Workflow paused (awaiting HITL or manual intervention)
- `COMPLETED`: All stages successfully completed
- `FAILED`: Workflow failed (after retries exhausted)
- `CANCELLED`: Workflow manually cancelled

### Stage States
- `PENDING`: Stage not yet started
- `IN_PROGRESS`: Stage currently executing
- `COMPLETED`: Stage successfully completed
- `FAILED`: Stage failed
- `RETRYING`: Stage being retried after failure

## Kafka Integration

### Consumes From
- `orchestrator_commands`: Commands to start/stop workflows
  - `start_daily_workflow`: Initiate daily automated workflow
  - `manual_trigger`: Manual workflow trigger for testing

### Produces To
- `discovery_queue`: Triggers for content discovery
- `factcheck_queue`: Triggers for fact checking (indirect, via Ingestion Service)
- `content_creation_queue`: Triggers for content creation
- `publication_queue`: Triggers for final publication

## Configuration
- `orchestrator.max_retries`: Maximum retries per stage (default: 3)
- `orchestrator.retry_delay_seconds`: Delay between retries (default: 60)
- `orchestrator.workflow_timeout_hours`: Maximum workflow duration (default: 24)

## Database Schema

### Tables Used
- `workflows`: Workflow metadata and history
- `workflow_stages`: Individual stage tracking
- `tasks`: Task definitions and parameters

### Redis Keys
- `workflow:{task_id}:state`: Current workflow state
- `workflow:{task_id}:stage:{stage_name}`: Stage state
- `task_count:{date}`: Daily task counter for ID generation

## API Contract

### Input (Kafka Message)
```json
{
  "command": "start_daily_workflow",
  "timestamp": "2025-10-22T08:00:00Z"
}
```

```json
{
  "command": "manual_trigger",
  "taskId": "task-20251022-001",
  "parameters": {
    "targetLocation": {
      "name": "Finland",
      "coordinates": [60.1699, 24.9384]
    }
  }
}
```

### State Machine Events
Internal state transitions published to `workflow_events` topic for monitoring.

## Running the Service

### Development
```bash
cd src/backend/services/orchestration_service
python src/main.py
```

### Docker
```bash
docker build -t clilens-orchestration-service .
docker run -e REDIS_URL=redis://redis:6379 clilens-orchestration-service
```

## Testing
```bash
pytest tests/test_orchestration.py
pytest tests/test_state_machine.py
```

## Logging
Structured logging with workflow context:
- `task_id`: Unique task identifier
- `workflow_status`: Current workflow state
- `stage_name`: Current stage being executed
- `retry_count`: Number of retries attempted

## Error Handling
- **Stage Failures**: Retry up to `max_retries` times with exponential backoff
- **Timeout Handling**: Workflows exceeding timeout are marked as failed
- **Partial Failures**: Individual stage failures don't cancel entire workflow
- **State Recovery**: Workflow state persisted in Redis for crash recovery

## Monitoring & Observability
- Workflow stage durations tracked
- Success/failure rates per stage
- Retry counts and patterns
- Workflow throughput metrics

## Future Enhancements
- Dynamic stage routing based on content type
- A/B testing support for different workflow configurations
- Advanced retry strategies (circuit breaker pattern)
- Workflow visualization dashboard
- Multi-tenant workflow isolation
