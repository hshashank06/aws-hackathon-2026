---
feature: appsync-streaming-search
created: 2024-03-08
status: draft
---

# AppSync Streaming Search - Implementation Tasks

## 1. Infrastructure Setup

### 1.1 Create AppSync API
- [ ] 1.1.1 Create AppSync GraphQL API in AWS Console
- [ ] 1.1.2 Create GraphQL schema file `aws/appsync/schema.graphql`
- [ ] 1.1.3 Deploy schema to AppSync API
- [ ] 1.1.4 Generate API Key for authentication
- [ ] 1.1.5 Configure CORS settings for UI domain
- [ ] 1.1.6 Document AppSync endpoint and API key

### 1.2 Create InvokerLambda Function
- [ ] 1.2.1 Create directory `aws/lambda/searchInvokerFunction/`
- [ ] 1.2.2 Create `lambda_function.py` with handler
- [ ] 1.2.3 Create `requirements.txt` (boto3)
- [ ] 1.2.4 Create IAM role with permissions:
  - [ ] Lambda invoke on WorkerLambda
  - [ ] DynamoDB PutItem on SearchResults
- [ ] 1.2.5 Deploy Lambda function
- [ ] 1.2.6 Configure environment variables:
  - [ ] WORKER_FUNCTION_NAME
  - [ ] DYNAMODB_TABLE_NAME
  - [ ] DYNAMODB_REGION
- [ ] 1.2.7 Test with sample event

### 1.3 Configure AppSync Resolvers
- [ ] 1.3.1 Create resolver for `initiateSearch` mutation → InvokerLambda
- [ ] 1.3.2 Create resolver for `publishAgentChunk` mutation → NONE (local)
- [ ] 1.3.3 Create resolver for `getSearchResults` query → DynamoDB or Lambda
- [ ] 1.3.4 Test resolvers in AppSync console

## 2. Backend Refactoring

### 2.1 Refactor searchFunction to WorkerLambda
- [ ] 2.1.1 Rename `aws/lambda/searchFunction/` to `aws/lambda/searchWorkerFunction/`
- [ ] 2.1.2 Update `lambda_function.py`:
  - [ ] Add AppSync publishing function
  - [ ] Add trace simplification function
  - [ ] Modify `invoke_bedrock_agent` to stream traces
  - [ ] Update main handler to accept InvokerLambda payload
  - [ ] Add error handling for AppSync failures
- [ ] 2.1.3 Update `requirements.txt`:
  - [ ] Add urllib3 (if not present)
- [ ] 2.1.4 Update IAM role with permissions:
  - [ ] appsync:GraphQL on AppSync API
- [ ] 2.1.5 Add environment variables:
  - [ ] APPSYNC_ENDPOINT
  - [ ] APPSYNC_API_KEY
- [ ] 2.1.6 Test with sample event from InvokerLambda

### 2.2 Update Deployment Scripts
- [ ] 2.2.1 Update `deploy.ps1`:
  - [ ] Add deployment for InvokerLambda
  - [ ] Update WorkerLambda deployment
- [ ] 2.2.2 Update `deploy.sh`:
  - [ ] Add deployment for InvokerLambda
  - [ ] Update WorkerLambda deployment
- [ ] 2.2.3 Create deployment script for AppSync schema
- [ ] 2.2.4 Test deployment scripts

### 2.3 Update API Gateway (Optional)
- [ ] 2.3.1 Decide: Keep REST endpoint or remove
- [ ] 2.3.2 If keeping: Update to proxy to AppSync
- [ ] 2.3.3 If removing: Document breaking change
- [ ] 2.3.4 Update API Gateway documentation

## 3. Frontend Implementation

### 3.1 Setup AppSync Client
- [ ] 3.1.1 Install dependencies:
  - [ ] `npm install @apollo/client graphql graphql-ws`
- [ ] 3.1.2 Create `app/src/app/services/appsync.ts`:
  - [ ] Configure Apollo Client
  - [ ] Setup HTTP link for queries/mutations
  - [ ] Setup WebSocket link for subscriptions
  - [ ] Export appsyncClient
- [ ] 3.1.3 Wrap App with ApolloProvider in `App.tsx`
- [ ] 3.1.4 Add environment variables to `app/.env.local`:
  - [ ] VITE_APPSYNC_ENDPOINT
  - [ ] VITE_APPSYNC_API_KEY
- [ ] 3.1.5 Test AppSync connection

### 3.2 Create GraphQL Operations
- [ ] 3.2.1 Create `app/src/app/services/graphql/operations.ts`
- [ ] 3.2.2 Define `INITIATE_SEARCH` mutation
- [ ] 3.2.3 Define `ON_AGENT_ACTIVITY` subscription
- [ ] 3.2.4 Define `GET_SEARCH_RESULTS` query
- [ ] 3.2.5 Export all operations

### 3.3 Create AgentActivityFeed Component
- [ ] 3.3.1 Create `app/src/app/components/AgentActivityFeed.tsx`
- [ ] 3.3.2 Implement subscription to `onAgentActivity`
- [ ] 3.3.3 Implement chunk display with timestamps
- [ ] 3.3.4 Implement auto-scroll to latest chunk
- [ ] 3.3.5 Implement completion detection
- [ ] 3.3.6 Implement error handling
- [ ] 3.3.7 Add animations with framer-motion
- [ ] 3.3.8 Style component with Tailwind CSS
- [ ] 3.3.9 Test component in isolation

### 3.4 Update Home Component
- [ ] 3.4.1 Import AppSync hooks and operations
- [ ] 3.4.2 Replace `searchHospitalsAPI` with `initiateSearch` mutation
- [ ] 3.4.3 Add state for `searchId`
- [ ] 3.4.4 Add `AgentActivityFeed` component
- [ ] 3.4.5 Implement `handleSearchComplete` callback
- [ ] 3.4.6 Implement `handleSearchError` callback
- [ ] 3.4.7 Fetch final results with `getSearchResults` query
- [ ] 3.4.8 Keep loading spinner visible during search
- [ ] 3.4.9 Test search flow end-to-end

### 3.5 Update API Service (Cleanup)
- [ ] 3.5.1 Remove `initiateSearch` function from `api.ts`
- [ ] 3.5.2 Remove `pollSearchStatus` function from `api.ts`
- [ ] 3.5.3 Remove `callSearchAPI` function from `api.ts`
- [ ] 3.5.4 Keep `getHospitalDoctorsAPI` (still needed)
- [ ] 3.5.5 Keep `adaptEnrichedHospitalToHospital` (still needed)
- [ ] 3.5.6 Update imports in components

## 4. Testing

### 4.1 Unit Tests
- [ ] 4.1.1 Test InvokerLambda:
  - [ ] Test searchId generation
  - [ ] Test DynamoDB write
  - [ ] Test async Lambda invocation
- [ ] 4.1.2 Test WorkerLambda:
  - [ ] Test trace simplification
  - [ ] Test chunk buffering
  - [ ] Test AppSync publishing
  - [ ] Test error handling
- [ ] 4.1.3 Test AgentActivityFeed:
  - [ ] Test subscription handling
  - [ ] Test chunk display
  - [ ] Test completion detection
  - [ ] Test error handling

### 4.2 Integration Tests
- [ ] 4.2.1 Test end-to-end search flow:
  - [ ] Submit search query
  - [ ] Verify InvokerLambda invoked
  - [ ] Verify WorkerLambda invoked
  - [ ] Verify chunks published to AppSync
  - [ ] Verify UI receives chunks
  - [ ] Verify results stored in DynamoDB
  - [ ] Verify UI displays results
- [ ] 4.2.2 Test hospital detail page:
  - [ ] Navigate to hospital detail
  - [ ] Verify data loaded from DynamoDB
  - [ ] Verify all fields display correctly
- [ ] 4.2.3 Test doctors lazy-loading:
  - [ ] Click "View Doctors" button
  - [ ] Verify doctors fetched from API
  - [ ] Verify doctors display correctly

### 4.3 Error Scenario Tests
- [ ] 4.3.1 Test Bedrock Agent timeout:
  - [ ] Simulate timeout
  - [ ] Verify error chunk published
  - [ ] Verify error stored in DynamoDB
  - [ ] Verify UI displays error
- [ ] 4.3.2 Test AppSync publish failure:
  - [ ] Simulate AppSync error
  - [ ] Verify retry logic
  - [ ] Verify search continues
  - [ ] Verify results still stored
- [ ] 4.3.3 Test WebSocket connection failure:
  - [ ] Simulate connection drop
  - [ ] Verify UI detects error
  - [ ] Verify fallback behavior
- [ ] 4.3.4 Test invalid search query:
  - [ ] Submit empty query
  - [ ] Verify validation error
  - [ ] Verify UI displays error

### 4.4 Performance Tests
- [ ] 4.4.1 Test single search latency:
  - [ ] Measure InvokerLambda response time
  - [ ] Measure chunk delivery latency
  - [ ] Measure total search time
  - [ ] Verify < 30s total
- [ ] 4.4.2 Test concurrent searches:
  - [ ] Run 10 concurrent searches
  - [ ] Verify all complete successfully
  - [ ] Measure average latency
- [ ] 4.4.3 Test load (100 concurrent searches):
  - [ ] Verify Lambda auto-scaling
  - [ ] Verify AppSync handles load
  - [ ] Measure error rate
  - [ ] Verify < 5% error rate

## 5. Documentation

### 5.1 Update Technical Documentation
- [ ] 5.1.1 Update `aws/lambda/searchWorkerFunction/README.md`:
  - [ ] Document new architecture
  - [ ] Document AppSync integration
  - [ ] Document environment variables
  - [ ] Update deployment instructions
- [ ] 5.1.2 Create `aws/lambda/searchInvokerFunction/README.md`:
  - [ ] Document purpose
  - [ ] Document input/output
  - [ ] Document environment variables
  - [ ] Document deployment
- [ ] 5.1.3 Create `aws/appsync/README.md`:
  - [ ] Document GraphQL schema
  - [ ] Document resolvers
  - [ ] Document authentication
  - [ ] Document testing

### 5.2 Update User Documentation
- [ ] 5.2.1 Update main `README.md`:
  - [ ] Document new search flow
  - [ ] Document environment variables
  - [ ] Update architecture diagram
- [ ] 5.2.2 Create migration guide:
  - [ ] Document breaking changes
  - [ ] Document migration steps
  - [ ] Document rollback procedure

### 5.3 Create Runbooks
- [ ] 5.3.1 Create deployment runbook:
  - [ ] Step-by-step deployment
  - [ ] Verification steps
  - [ ] Rollback procedure
- [ ] 5.3.2 Create troubleshooting runbook:
  - [ ] Common issues
  - [ ] Debugging steps
  - [ ] CloudWatch log queries

## 6. Deployment

### 6.1 Pre-Deployment Checklist
- [ ] 6.1.1 All tests passing
- [ ] 6.1.2 Code reviewed
- [ ] 6.1.3 Documentation updated
- [ ] 6.1.4 Environment variables configured
- [ ] 6.1.5 IAM roles created
- [ ] 6.1.6 CloudWatch alarms configured
- [ ] 6.1.7 Rollback plan documented

### 6.2 Deploy Backend
- [ ] 6.2.1 Deploy AppSync API:
  - [ ] Create API
  - [ ] Deploy schema
  - [ ] Create API key
  - [ ] Configure resolvers
- [ ] 6.2.2 Deploy InvokerLambda:
  - [ ] Create function
  - [ ] Configure environment variables
  - [ ] Attach IAM role
  - [ ] Test with sample event
- [ ] 6.2.3 Deploy WorkerLambda:
  - [ ] Update function code
  - [ ] Configure environment variables
  - [ ] Update IAM role
  - [ ] Test with sample event
- [ ] 6.2.4 Verify backend:
  - [ ] Test AppSync mutations
  - [ ] Test Lambda invocations
  - [ ] Check CloudWatch logs

### 6.3 Deploy Frontend
- [ ] 6.3.1 Update environment variables:
  - [ ] Add VITE_APPSYNC_ENDPOINT
  - [ ] Add VITE_APPSYNC_API_KEY
- [ ] 6.3.2 Build production bundle:
  - [ ] Run `npm run build`
  - [ ] Verify no errors
- [ ] 6.3.3 Deploy to hosting:
  - [ ] Upload build artifacts
  - [ ] Verify deployment
- [ ] 6.3.4 Verify frontend:
  - [ ] Test search flow
  - [ ] Test agent activity feed
  - [ ] Test hospital detail page
  - [ ] Test doctors lazy-loading

### 6.4 Post-Deployment Verification
- [ ] 6.4.1 Run smoke tests:
  - [ ] Submit test search
  - [ ] Verify chunks stream
  - [ ] Verify results display
- [ ] 6.4.2 Monitor CloudWatch:
  - [ ] Check Lambda logs
  - [ ] Check AppSync logs
  - [ ] Check error rates
- [ ] 6.4.3 Monitor metrics:
  - [ ] Search latency
  - [ ] Error rate
  - [ ] Concurrent executions
- [ ] 6.4.4 Verify hospital detail page
- [ ] 6.4.5 Verify doctors lazy-loading

## 7. Monitoring & Maintenance

### 7.1 Setup Monitoring
- [ ] 7.1.1 Create CloudWatch dashboard:
  - [ ] Search metrics
  - [ ] Lambda metrics
  - [ ] AppSync metrics
  - [ ] Error rates
- [ ] 7.1.2 Create CloudWatch alarms:
  - [ ] High error rate (> 5%)
  - [ ] High latency (> 35s)
  - [ ] Lambda throttling
  - [ ] DynamoDB throttling
- [ ] 7.1.3 Configure SNS notifications:
  - [ ] Email alerts
  - [ ] Slack integration (optional)

### 7.2 Ongoing Maintenance
- [ ] 7.2.1 Monitor CloudWatch logs daily
- [ ] 7.2.2 Review error rates weekly
- [ ] 7.2.3 Optimize performance based on metrics
- [ ] 7.2.4 Rotate AppSync API key quarterly
- [ ] 7.2.5 Update dependencies monthly

## 8. Cleanup (Optional)

### 8.1 Remove Old Code
- [ ] 8.1.1 Remove old `searchFunction` directory (if renamed)
- [ ] 8.1.2 Remove polling logic from `api.ts`
- [ ] 8.1.3 Remove unused test files
- [ ] 8.1.4 Remove old deployment scripts

### 8.2 Remove Old Infrastructure
- [ ] 8.2.1 Remove old API Gateway routes (if not needed)
- [ ] 8.2.2 Remove old CloudWatch log groups
- [ ] 8.2.3 Remove old IAM roles (if not needed)

## Task Summary

**Total Tasks**: 150+
**Estimated Time**: 3-5 days
**Priority**: High
**Risk**: Medium (breaking changes)

## Dependencies

- AWS AppSync API created
- InvokerLambda deployed
- WorkerLambda refactored
- UI dependencies installed
- Environment variables configured

## Success Criteria

- [ ] Users see real-time agent activity
- [ ] Search completes within 30 seconds
- [ ] Hospital results display correctly
- [ ] Hospital detail page works unchanged
- [ ] Doctors lazy-loading works unchanged
- [ ] Error rate < 5%
- [ ] All tests passing
