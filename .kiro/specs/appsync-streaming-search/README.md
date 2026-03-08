# AppSync Streaming Search - Specification

## Overview

This specification describes the migration from polling-based search to real-time streaming using AWS AppSync subscriptions. Users will see live AI agent activity as the system searches for hospitals.

## Documents

1. **[requirements.md](./requirements.md)** - User stories, acceptance criteria, and functional requirements
2. **[design.md](./design.md)** - Architecture, component design, and implementation details
3. **[tasks.md](./tasks.md)** - Step-by-step implementation tasks

## Quick Summary

### Current Architecture (Polling)
```
UI → POST /search → searchFunction → DynamoDB
UI → GET /search/{id} (poll every 5s) → DynamoDB → UI
```

### New Architecture (Streaming)
```
UI → AppSync initiateSearch → InvokerLambda → WorkerLambda
WorkerLambda → Bedrock Agent (with trace)
WorkerLambda → AppSync publishChunk (real-time)
UI subscribes → onAgentActivity → displays chunks
WorkerLambda → DynamoDB (final results)
UI → getSearchResults → displays hospitals
```

## Key Changes

### Backend
- **New**: InvokerLambda - Receives search requests, invokes WorkerLambda async
- **Refactored**: searchFunction → WorkerLambda - Streams agent activity to AppSync
- **New**: AppSync API - GraphQL API for mutations and subscriptions

### Frontend
- **New**: AppSync Client - Apollo Client with WebSocket support
- **New**: AgentActivityFeed Component - Displays streaming agent activity
- **Updated**: Home Component - Uses AppSync instead of polling
- **Removed**: Polling logic from api.ts

## Breaking Changes

1. **REST API**: `POST /search` replaced with AppSync mutation
2. **Lambda**: searchFunction split into InvokerLambda + WorkerLambda
3. **Environment Variables**: New AppSync config required in UI

## What Stays the Same

- Hospital detail page (reads from DynamoDB)
- Doctors lazy-loading endpoint
- DynamoDB schema
- User location tracking
- Distance calculation

## Implementation Timeline

- **Phase 1**: Infrastructure Setup (1 day)
  - Create AppSync API
  - Create InvokerLambda
  - Refactor WorkerLambda

- **Phase 2**: Frontend Integration (1 day)
  - Setup AppSync client
  - Create AgentActivityFeed
  - Update Home component

- **Phase 3**: Testing (1 day)
  - Unit tests
  - Integration tests
  - Performance tests

- **Phase 4**: Deployment (1 day)
  - Deploy backend
  - Deploy frontend
  - Monitor and verify

**Total**: 3-5 days

## Success Metrics

- Users see real-time agent activity ✓
- Search completes < 30 seconds ✓
- Error rate < 5% ✓
- Hospital detail page works ✓
- Doctors lazy-loading works ✓

## Getting Started

1. Read [requirements.md](./requirements.md) for user stories
2. Review [design.md](./design.md) for architecture
3. Follow [tasks.md](./tasks.md) for implementation

## Questions?

See the design document for detailed architecture diagrams, code examples, and error handling strategies.
