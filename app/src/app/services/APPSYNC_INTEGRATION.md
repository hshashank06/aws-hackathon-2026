# AppSync Streaming Integration Guide

## Overview
The UI now integrates with AWS AppSync for real-time streaming of AI agent activity during hospital search.

## Architecture Flow

```
User Search → AppSync Mutation (initiateSearch)
           ↓
       SearchId returned
           ↓
   Subscribe to onAgentActivity(searchId)
           ↓
   Receive real-time chunks from WorkerLambda
           ↓
   Display in AgentActivityStream component
           ↓
   Poll getSearchResults until status = "complete"
           ↓
   Display final enriched hospital results
```

## Files Created

### 1. `app/src/app/services/appsync.ts`
- AppSync client configuration using AWS Amplify
- GraphQL operations: `initiateSearch`, `subscribeToAgentActivity`, `getSearchResults`
- Type definitions for all AppSync responses

### 2. `app/src/app/components/AgentActivityStream.tsx`
- Real-time activity display component
- Shows agent thinking process with emojis (🚀 💭 🤔 ✓ 🔍 📊 ✅)
- Auto-scrolls as new chunks arrive
- Animated typing indicator when active
- Semi-transparent "thinking container" style

### 3. Updated `app/src/app/pages/Home.tsx`
- Integrated AppSync streaming into search flow
- Manages subscription lifecycle (subscribe/unsubscribe)
- Displays AgentActivityStream alongside loading spinner
- Polls for final results after streaming completes

## Usage

### Search Flow

1. User enters query and clicks Search
2. UI calls `AppSync.initiateSearch()` → receives `searchId`
3. UI subscribes to `AppSync.subscribeToAgentActivity(searchId)`
4. As WorkerLambda processes:
   - Chunks are published via `publishAgentChunk` mutation
   - AppSync pushes chunks to subscribed clients
   - UI displays chunks in AgentActivityStream component
5. UI polls `AppSync.getSearchResults(searchId)` every 2 seconds
6. When status = "complete":
   - Unsubscribe from activity stream
   - Display final enriched hospital results

### Component Integration

```tsx
import { AgentActivityStream } from "../components/AgentActivityStream";

// In your component
const [agentChunks, setAgentChunks] = useState<string[]>([]);
const [isStreaming, setIsStreaming] = useState(false);

// Subscribe to activity
const subscription = AppSync.subscribeToAgentActivity(
  searchId,
  (chunk) => {
    setAgentChunks((prev) => [...prev, chunk.chunk]);
  }
);

// Render
<AgentActivityStream chunks={agentChunks} isActive={isStreaming} />
```

## Configuration

### Environment Variables
Add to `.env.local`:
```bash
VITE_APPSYNC_ENDPOINT=https://xg5bjurpsbgfda2nufr6c46n7e.appsync-api.us-east-1.amazonaws.com/graphql
VITE_APPSYNC_REGION=us-east-1
VITE_APPSYNC_API_KEY=da2-ezoxtcpclffrdkbysmv22sjiei
```

### Dependencies
Already installed:
- `aws-amplify` (v6.16.2) - AppSync client
- `motion` (v12.23.24) - Animations

## Testing

1. Start dev server: `npm run dev`
2. Navigate to home page
3. Enter search query (e.g., "cardiac surgery")
4. Observe:
   - Agent activity stream appears below search bar
   - Real-time chunks display with emojis
   - Loading spinner shows alongside activity
   - Final results appear when complete

## Troubleshooting

### Subscription not receiving chunks
- Check AppSync API key is valid
- Verify WorkerLambda is publishing chunks
- Check browser console for subscription errors

### Chunks not displaying
- Verify `AgentActivityStream` component is rendered
- Check `agentChunks` state is updating
- Ensure `isStreaming` is set to `true`

### Results not loading
- Check polling logic in `handleSearch`
- Verify `getSearchResults` query returns data
- Check DynamoDB has enriched hospital data

## Future Enhancements

1. Add error handling UI for failed searches
2. Show AI summary in a separate card
3. Add "Stop Search" button to cancel in-progress searches
4. Persist activity log for completed searches
5. Add sound/notification when search completes
