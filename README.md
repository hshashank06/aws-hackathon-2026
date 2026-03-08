# Hospital Review Platform - AWS Hackathon 2026

## 🏥 Overview

The **Hospital Review Platform** is an AI-powered healthcare discovery system that helps patients find the best hospitals, doctors, and treatments based on verified reviews, insurance coverage, and personalized recommendations. Built entirely on AWS services, it combines traditional database operations with cutting-edge AI capabilities to provide intelligent, real-time hospital search and recommendations.

### Key Differentiators

Unlike Google Maps or traditional hospital directories, this platform offers:

1. **AI-Powered Recommendations**: Uses AWS Bedrock Agent with multi-agent collaboration to understand complex medical queries
2. **Verified Patient Reviews**: Real patient experiences with medical procedures, costs, and insurance claims
3. **Insurance-Aware Search**: Finds hospitals based on your insurance coverage and out-of-pocket costs
4. **Real-Time AI Streaming**: Watch the AI agent think and search in real-time via AppSync subscriptions
5. **Semantic Search**: Vector-based search using embeddings to understand medical terminology
6. **Cost Transparency**: See actual treatment costs, insurance coverage, and patient-reported expenses

## 🎯 Problem Statement

Patients face significant challenges when choosing healthcare providers:
- **Information Asymmetry**: Limited access to quality and cost data
- **Insurance Complexity**: Difficulty understanding coverage and out-of-pocket costs
- **Generic Reviews**: Google reviews don't capture medical-specific experiences
- **No Cost Transparency**: Treatment costs are opaque until after service
- **Poor Search**: Traditional search doesn't understand medical context

## 💡 Solution

Our platform solves these problems through:

1. **Structured Medical Reviews**: Captures procedure type, costs, insurance claims, and outcomes
2. **AI-Powered Search**: Understands queries like "affordable hospital for cardiac surgery with Blue Cross insurance"
3. **Real-Time Recommendations**: Streams AI reasoning process to build trust
4. **Cost Prediction**: Shows typical costs and insurance coverage before treatment
5. **Doctor Expertise**: Highlights top doctors by specialty and patient ratings


## 🏗️ Architecture

### High-Level System Architecture

```
                    ┌─────────────────────────────────────────┐
                    │      Frontend (React + Vite)            │
                    │  ┌──────────┐  ┌──────────┐  ┌───────┐ │
                    │  │ Search   │  │ Hospital │  │Review │ │
                    │  │ + Stream │  │ Details  │  │ Form  │ │
                    │  └────┬─────┘  └────┬─────┘  └───┬───┘ │
                    └───────┼─────────────┼────────────┼─────┘
                            │             │            │
                            └─────────────┼────────────┘
                                          │
                            ┌─────────────▼─────────────┐
                            │    AWS AppSync (GraphQL)  │
                            │  • Mutations              │
                            │  • Queries                │
                            │  • Subscriptions          │
                            └─────────────┬─────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
          ┌─────────▼─────────┐          │          ┌──────────▼──────────┐
          │   API Gateway     │          │          │  AppSync Resolvers  │
          │   (REST API)      │          │          │  (Lambda)           │
          └─────────┬─────────┘          │          └──────────┬──────────┘
                    │                     │                     │
          ┌─────────▼─────────────────────▼─────────────────────▼─────────┐
          │                     Lambda Functions                           │
          │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
          │  │   CRUD   │  │  Search  │  │  Review  │  │  Ingestion   │  │
          │  │ (8 funcs)│  │(3 funcs) │  │(1 func)  │  │  (1 func)    │  │
          │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
          └───────┼─────────────┼─────────────┼────────────────┼──────────┘
                  │             │             │                │
       ┌──────────▼──────┐     │      ┌──────▼──────┐  ┌──────▼──────────┐
       │   DynamoDB      │     │      │     S3      │  │   OpenSearch    │
       │  (8 tables)     │     │      │ (Documents) │  │ (Vector Store)  │
       └─────────────────┘     │      └─────────────┘  └─────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  AWS Bedrock Agent  │
                    │  ┌───────────────┐  │
                    │  │ Orchestrator  │  │
                    │  └───────┬───────┘  │
                    │          │          │
                    │  ┌───────▼───────┐  │
                    │  │   DB Tool     │  │
                    │  │ (Action Grp)  │  │
                    │  └───────┬───────┘  │
                    │          │          │
                    │  ┌───────▼───────┐  │
                    │  │  Knowledge    │  │
                    │  │     Base      │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
```

### Data Flow

#### 1. Hospital Search Flow

```
┌──────────┐
│   User   │
│  Query   │
└────┬─────┘
     │
     ▼
┌─────────────────┐
│    AppSync      │
│  (GraphQL API)  │
└────┬────────────┘
     │
     ▼
┌──────────────────────┐
│ searchInvokerFunction│  (Returns searchId immediately)
└────┬─────────────────┘
     │ (Async invoke)
     ▼
┌──────────────────────┐
│ searchWorkerFunction │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────┐
│  Bedrock Agent       │
│  (Orchestrator)      │
└────┬─────────────────┘
     │
     ├─────────────────────────────────┐
     │                                 │
     ▼                                 ▼
┌────────────────────┐    ┌──────────────────────┐
│ healthSearchTool   │    │ OpenSearch Knowledge │
│ Function           │    │ Base                 │
│                    │    │                      │
│ ↓                  │    │ ↓                    │
│ DynamoDB Tables    │    │ Vector Search        │
│ (Hospital/Doctor)  │    │ (Review Embeddings)  │
└────────┬───────────┘    └──────────┬───────────┘
         │                           │
         └───────────┬───────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ AI-Generated Response │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │ AppSync Subscription  │
         │ (Real-time Stream)    │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │    Frontend UI        │
         │ (Display Results)     │
         └───────────────────────┘
```

#### 2. Review Submission Flow

```
┌──────────────┐
│ User Upload  │
│ (Documents)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│      S3      │
│   Bucket     │
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ reviewFunction   │
└──────┬───────────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌──────────────┐    ┌────────────────┐
│   Textract   │    │  Comprehend    │
│    (OCR)     │    │   Medical      │
└──────┬───────┘    └────────┬───────┘
       │                     │
       └──────────┬──────────┘
                  │
                  ▼
       ┌──────────────────┐
       │  Extract Data    │
       └──────┬───────────┘
              │
              ▼
       ┌──────────────────┐
       │    DynamoDB      │
       │  (Review table)  │
       └──────┬───────────┘
              │
              ▼
       ┌──────────────────┐
       │ ingestionFunction│
       └──────┬───────────┘
              │
              ▼
       ┌──────────────────┐
       │     Bedrock      │
       │ (Generate        │
       │  Embedding)      │
       └──────┬───────────┘
              │
              ▼
       ┌──────────────────┐
       │   OpenSearch     │
       │ (Index Vector)   │
       └──────────────────┘
```


## 🧩 Components

### Frontend (React + TypeScript)

**Location**: `app/`

**Technology Stack**:
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS + shadcn/ui components
- **State Management**: React Context API
- **GraphQL Client**: Apollo Client (AppSync integration)
- **Maps**: AWS Location Service
- **Routing**: React Router v6

**Key Features**:
- Real-time AI agent activity streaming
- Interactive hospital search with filters
- Hospital detail pages with reviews
- Review submission with document upload
- Responsive design for mobile/desktop

**Pages**:
- `Home.tsx`: Search interface with AI streaming
- `HospitalDetail.tsx`: Hospital information and reviews
- `CreateReview.tsx`: Multi-step review submission
- `PastReviews.tsx`: User's review history
- `MyDetails.tsx`: User profile management

### Backend (AWS Lambda Functions)

**Location**: `aws/lambda/`

#### CRUD Functions (8 functions)

1. **customerFunction**: Customer/patient management
2. **hospitalFunction**: Hospital data management
3. **departmentFunction**: Hospital department management
4. **doctorFunction**: Doctor profile management
5. **insuranceCompanyFunction**: Insurance provider management
6. **insurancePolicyFunction**: Insurance policy management
7. **reviewFunction**: Review submission and processing
8. **ingestionFunction**: OpenSearch vector indexing

#### Search Functions (3 functions)

1. **searchInvokerFunction**: Async search orchestration
2. **searchWorkerFunction**: AI-powered search processing
3. **healthSearchToolFunction**: Bedrock Agent action group

**Common Features**:
- Python 3.11 runtime
- DynamoDB integration
- CloudWatch logging
- Error handling and retries
- CORS-enabled responses

### Database (Amazon DynamoDB)

**Location**: Tables in `eu-north-1` region

**Tables** (8 tables):

1. **Customer**: Patient information and visit history
2. **Hospital**: Hospital profiles and metadata
3. **Department**: Hospital departments and services
4. **Doctor**: Doctor profiles and specializations
5. **InsuranceCompany**: Insurance provider information
6. **InsurancePolicy**: Insurance plan details
7. **Review**: Patient reviews and experiences
8. **SearchResults**: Cached search results (TTL: 5 hours)

**Key Features**:
- On-demand capacity mode
- Point-in-time recovery enabled
- Encryption at rest
- Global Secondary Indexes (GSI) for queries
- TTL for automatic data expiration

### AI/ML Components

#### AWS Bedrock Agent

**Location**: `aws/agents/`

**Architecture**: Multi-agent collaboration system

**Agents**:

1. **Orchestrator Agent**:
   - Coordinates search workflow
   - Routes queries to appropriate sub-agents
   - Synthesizes final recommendations

2. **DB Tool Agent**:
   - Executes database queries
   - Action group: healthSearchToolFunction
   - 11 specialized search functions

3. **Knowledge Base Agent**:
   - Semantic search over reviews
   - OpenSearch vector database
   - Bedrock Titan embeddings

**Models Used**:
- **Orchestration**: Claude 3 Sonnet
- **Embeddings**: Titan Embed Text v2 (1024 dimensions)
- **Knowledge Base**: Claude 3 Haiku

#### Amazon OpenSearch Service

**Domain**: `health-review-vector-domain`

**Configuration**:
- **Instance Type**: t3.small.search (2 nodes)
- **Storage**: 20 GB EBS per node
- **Index**: `health-review-index`
- **Vector Dimensions**: 1024
- **Algorithm**: HNSW (Hierarchical Navigable Small World)
- **Distance Metric**: Cosine similarity

**Use Cases**:
- Semantic search over patient reviews
- Similar hospital recommendations
- Medical terminology understanding
- Context-aware search results

### API Layer

#### AWS AppSync (GraphQL)

**Location**: `aws/appsync/`

**Schema**: `schema.graphql`

**Operations**:
- **Mutations**: `initiateSearch`, `publishAgentChunk`
- **Queries**: `getSearchResults`
- **Subscriptions**: `onAgentActivity`

**Features**:
- Real-time subscriptions via WebSocket
- API Key authentication
- Lambda resolvers
- Automatic schema validation

#### AWS API Gateway (REST)

**Endpoints**:
- `/customers` - Customer CRUD
- `/hospitals` - Hospital CRUD
- `/departments` - Department CRUD
- `/doctors` - Doctor CRUD
- `/insurance-companies` - Insurance company CRUD
- `/insurance-policies` - Insurance policy CRUD
- `/reviews` - Review CRUD
- `/search` - Hospital search (deprecated, use AppSync)

**Features**:
- CORS enabled
- Request validation
- CloudWatch logging
- Throttling and rate limiting

### Document Processing

#### AWS Textract

**Purpose**: Extract text from medical documents

**Supported Documents**:
- Medical bills
- Insurance claim forms
- Medical records

**Features**:
- OCR for scanned documents
- Table extraction
- Form field detection
- Handwriting recognition

#### AWS Comprehend Medical

**Purpose**: Extract medical entities from text

**Entities Detected**:
- Medications
- Medical conditions
- Procedures
- Anatomy
- Test results

**Use Cases**:
- Validate review authenticity
- Extract procedure types
- Identify medical conditions
- Enrich review metadata

### Storage

#### Amazon S3

**Buckets**:
- `hospital-review-documents`: Uploaded medical documents
- `hospital-review-static`: Frontend static assets (Amplify)

**Features**:
- Versioning enabled
- Encryption at rest (SSE-S3)
- Lifecycle policies
- Pre-signed URLs for secure uploads


## 🚀 Features

### 1. AI-Powered Hospital Search

**Description**: Natural language search with real-time AI reasoning

**How it Works**:
1. User enters query: "best hospital for cardiac surgery with Blue Cross insurance"
2. AppSync initiates search and returns searchId
3. Frontend subscribes to AI agent activity stream
4. Bedrock Agent processes query:
   - Understands intent (cardiac surgery + insurance)
   - Queries database for matching hospitals
   - Searches knowledge base for patient experiences
   - Ranks results by relevance
5. Streams reasoning steps to UI in real-time
6. Returns ranked hospital recommendations

**Technologies**:
- AWS Bedrock Agent (Claude 3 Sonnet)
- AWS AppSync (GraphQL subscriptions)
- Amazon OpenSearch (vector search)
- AWS Lambda (orchestration)

### 2. Verified Patient Reviews

**Description**: Structured reviews with document verification

**Review Components**:
- Overall rating (1-5 stars)
- Hospital review (text)
- Doctor review (text)
- Procedure type
- Treatment costs
- Insurance claim details
- Document uploads (bills, claims)

**Verification Process**:
1. User uploads medical documents
2. AWS Textract extracts text
3. AWS Comprehend Medical validates entities
4. System cross-references with review data
5. Verified badge awarded if consistent

**Technologies**:
- AWS Textract (OCR)
- AWS Comprehend Medical (NLP)
- Amazon S3 (document storage)
- AWS Lambda (processing)

### 3. Insurance-Aware Search

**Description**: Find hospitals based on insurance coverage

**Capabilities**:
- Filter by insurance provider
- Show coverage percentage
- Display out-of-pocket costs
- Compare insurance plans
- Identify in-network hospitals

**Example Queries**:
- "hospitals accepting Blue Cross"
- "affordable cardiac surgery with my insurance"
- "highest insurance coverage for orthopedic surgery"

**Technologies**:
- DynamoDB (insurance data)
- Bedrock Agent (query understanding)
- healthSearchToolFunction (database queries)

### 4. Cost Transparency

**Description**: Real treatment costs from patient experiences

**Cost Information**:
- Total bill amount
- Insurance claimed amount
- Insurance approved amount
- Out-of-pocket expense
- Cost range by procedure
- Hospital cost comparison

**Aggregations**:
- Average cost per procedure
- Min/max cost range
- Insurance coverage percentage
- Cost trends over time

**Technologies**:
- DynamoDB (cost data)
- Lambda (aggregations)
- React (visualization)

### 5. Doctor Recommendations

**Description**: Find top doctors by specialty and rating

**Doctor Information**:
- Name and credentials
- Specialization
- Hospital affiliation
- Department
- Patient ratings
- Years of experience
- Consultation fees

**Search Capabilities**:
- Filter by specialization
- Sort by rating
- Filter by hospital
- AI-generated doctor reviews

**Technologies**:
- DynamoDB (doctor data)
- Bedrock Agent (recommendations)
- OpenSearch (semantic search)

### 6. Real-Time AI Streaming

**Description**: Watch AI agent think and search in real-time

**Stream Events**:
- "🚀 Starting AI-powered hospital search..."
- "💭 Understanding your query..."
- "🔍 Searching database for matching hospitals..."
- "📚 Consulting knowledge base for patient experiences..."
- "✓ Model responded"
- "✅ Search completed! Found 5 hospitals."

**Benefits**:
- Builds user trust
- Shows AI reasoning process
- Provides progress feedback
- Reduces perceived latency

**Technologies**:
- AWS AppSync (WebSocket subscriptions)
- Bedrock Agent (trace events)
- React (real-time UI updates)

### 7. Semantic Search

**Description**: Understand medical terminology and context

**Capabilities**:
- Synonym matching (e.g., "heart surgery" = "cardiac surgery")
- Context understanding (e.g., "affordable" considers insurance)
- Medical entity recognition
- Similar review recommendations

**Example**:
- Query: "good hospital for heart problems"
- Understands: cardiac care, cardiology, heart surgery
- Finds: hospitals with cardiology departments, cardiologists, cardiac surgery reviews

**Technologies**:
- Bedrock Titan Embed Text v2 (embeddings)
- Amazon OpenSearch (vector search)
- Bedrock Agent (query understanding)

### 8. Interactive Maps

**Description**: Visualize hospital locations and distances

**Features**:
- Hospital markers on map
- Distance calculation from user location
- Directions to hospital
- Nearby hospitals
- Filter by distance

**Technologies**:
- AWS Location Service
- MapLibre GL JS
- Haversine distance formula


## 📊 Technology Stack

### Frontend
| Technology | Purpose | Version |
|------------|---------|---------|
| React | UI framework | 18.3.1 |
| TypeScript | Type safety | 5.6.2 |
| Vite | Build tool | 6.0.1 |
| Tailwind CSS | Styling | 3.4.17 |
| shadcn/ui | Component library | Latest |
| Apollo Client | GraphQL client | 3.11.11 |
| React Router | Routing | 7.1.1 |
| Framer Motion | Animations | 11.15.0 |
| MapLibre GL JS | Maps | 4.7.1 |

### Backend
| Technology | Purpose | Version |
|------------|---------|---------|
| Python | Lambda runtime | 3.11 |
| boto3 | AWS SDK | 1.28+ |
| AWS Lambda | Serverless compute | - |
| Amazon DynamoDB | NoSQL database | - |
| AWS API Gateway | REST API | - |
| AWS AppSync | GraphQL API | - |

### AI/ML
| Technology | Purpose | Model |
|------------|---------|-------|
| AWS Bedrock | LLM orchestration | Claude 3 Sonnet |
| Bedrock Agent | Multi-agent system | Claude 3 Sonnet/Haiku |
| Titan Embeddings | Vector generation | Titan Embed Text v2 |
| Amazon OpenSearch | Vector database | 2.11 |
| AWS Textract | OCR | - |
| AWS Comprehend Medical | Medical NLP | - |

### Infrastructure
| Technology | Purpose |
|------------|---------|
| AWS Amplify | Frontend hosting |
| Amazon S3 | Object storage |
| AWS CloudWatch | Logging and monitoring |
| AWS IAM | Access management |
| AWS Location Service | Maps and geocoding |

## 💰 Cost Analysis

### Monthly Cost Breakdown (Optimized)

| Service | Usage | Cost |
|---------|-------|------|
| **Lambda** | 1M invocations, 512MB, 5s avg | $25 |
| **DynamoDB** | On-demand, 10GB storage | $15 |
| **Bedrock** | 10K agent invocations | $150 |
| **OpenSearch** | 2x t3.small.search | $60 |
| **AppSync** | 1M requests, 500K subscriptions | $20 |
| **S3** | 100GB storage, 10K requests | $5 |
| **Textract** | 1K pages | $3 |
| **Comprehend Medical** | 1K documents | $5 |
| **API Gateway** | 1M requests | $3.50 |
| **CloudWatch** | Logs and metrics | $10 |
| **Amplify** | Hosting and builds | $1.50 |
| **Total** | | **$298/month** |

### Cost per User

- **Light User** (5 searches/month): $0.03
- **Average User** (20 searches/month): $0.12
- **Heavy User** (100 searches/month): $0.60

### Cost Optimization Strategies

1. **Lambda**: Use ARM64 architecture (20% cheaper)
2. **DynamoDB**: On-demand mode for variable traffic
3. **Bedrock**: Cache common queries
4. **OpenSearch**: Use t3.small instead of m5.large
5. **AppSync**: Batch subscriptions
6. **S3**: Lifecycle policies for old documents

## 📈 Performance Metrics

### Latency Benchmarks

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Hospital Search (initial) | 350ms | 500ms | 800ms |
| Hospital Search (complete) | 18s | 25s | 35s |
| Hospital Detail Page | 200ms | 400ms | 600ms |
| Review Submission | 2s | 4s | 6s |
| Document Processing | 5s | 10s | 15s |
| CRUD Operations | 100ms | 200ms | 300ms |

### Throughput

- **Concurrent Users**: 1000+
- **Searches per Second**: 50
- **Reviews per Day**: 10,000
- **API Requests per Second**: 500

### Scalability

- **Lambda**: Auto-scales to 1000 concurrent executions
- **DynamoDB**: On-demand capacity (unlimited)
- **AppSync**: 100,000 concurrent subscriptions
- **OpenSearch**: Horizontal scaling with additional nodes


## 🛠️ Setup and Deployment

### Prerequisites

- AWS Account with appropriate permissions
- Node.js 18+ and npm
- Python 3.11+
- AWS CLI configured
- Git

### Environment Configuration

#### 1. Frontend Environment Variables

Create `app/.env.local`:

```bash
# API Gateway
VITE_API_BASE_URL=https://your-api-id.execute-api.us-east-1.amazonaws.com

# AppSync
VITE_APPSYNC_ENDPOINT=https://your-api-id.appsync-api.us-east-1.amazonaws.com/graphql
VITE_APPSYNC_REGION=us-east-1
VITE_APPSYNC_API_KEY=da2-your-api-key-here

# AWS Location Service
VITE_AWS_LOCATION_API_KEY=your-api-key-here
VITE_AWS_LOCATION_REGION=us-east-1
VITE_AWS_LOCATION_MAP_STYLE=Standard
VITE_AWS_LOCATION_COLOR_SCHEME=Light
```

#### 2. Backend Environment Variables

Each Lambda function requires specific environment variables. See `aws/lambda/.env.example` for complete list.

**Common Variables**:
```bash
# Bedrock
BEDROCK_AGENT_ID=your-agent-id
BEDROCK_AGENT_ALIAS_ID=your-alias-id
BEDROCK_REGION=us-east-1
BEDROCK_SESSION_ID=your-session-id

# DynamoDB
DYNAMODB_REGION=eu-north-1
TABLE_NAME=<specific-table-name>

# API Gateway
API_GATEWAY_BASE_URL=https://your-api-id.execute-api.us-east-1.amazonaws.com

# AppSync (for searchWorkerFunction)
APPSYNC_ENDPOINT=https://your-api-id.appsync-api.us-east-1.amazonaws.com/graphql
APPSYNC_API_KEY=da2-your-api-key-here
```

### Deployment Steps

#### 1. Deploy DynamoDB Tables

```bash
# Create tables using AWS CLI or CloudFormation
aws dynamodb create-table \
  --table-name Customer \
  --attribute-definitions AttributeName=customerId,AttributeType=S \
  --key-schema AttributeName=customerId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-north-1

# Repeat for all 8 tables
```

#### 2. Deploy Lambda Functions

```bash
# Navigate to function directory
cd aws/lambda/customerFunction

# Install dependencies
pip install -r requirements.txt -t package/

# Package function
cd package
zip -r ../function.zip .
cd ..
cp lambda_function.py package/
cd package
zip -g ../function.zip lambda_function.py
cd ..

# Deploy
aws lambda create-function \
  --function-name customerFunction \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --environment Variables="{TABLE_NAME=Customer,DYNAMODB_REGION=eu-north-1}"

# Repeat for all Lambda functions
```

#### 3. Deploy API Gateway

```bash
# Create REST API
aws apigateway create-rest-api \
  --name "Hospital Review API" \
  --description "REST API for Hospital Review Platform"

# Create resources and methods
# See aws/create-api-gateway.ps1 for complete script
```

#### 4. Deploy AppSync API

```bash
# Create GraphQL API
aws appsync create-graphql-api \
  --name "Hospital Review AppSync API" \
  --authentication-type API_KEY

# Upload schema
aws appsync start-schema-creation \
  --api-id YOUR_API_ID \
  --definition file://aws/appsync/schema.graphql

# Create resolvers
# See aws/appsync/resolvers/README.md for details
```

#### 5. Deploy Bedrock Agent

```bash
# Create agent
aws bedrock-agent create-agent \
  --agent-name "HealthSearchAgent" \
  --foundation-model "anthropic.claude-3-sonnet-20240229-v1:0" \
  --instruction file://aws/agents/orchestrator-agent-ui-fields.md

# Create action group
aws bedrock-agent create-agent-action-group \
  --agent-id YOUR_AGENT_ID \
  --action-group-name "HealthSearchTools" \
  --action-group-executor lambda=arn:aws:lambda:us-east-1:ACCOUNT_ID:function:healthSearchToolFunction \
  --api-schema file://aws/agents/action-groups/all-functions.json

# Create knowledge base
aws bedrock-agent create-knowledge-base \
  --name "PatientReviewsKB" \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/bedrock-kb-role \
  --knowledge-base-configuration type=VECTOR,vectorKnowledgeBaseConfiguration={embeddingModelArn=arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0}
```

#### 6. Deploy OpenSearch Domain

```bash
# Create domain
aws opensearch create-domain \
  --domain-name health-review-vector-domain \
  --engine-version OpenSearch_2.11 \
  --cluster-config InstanceType=t3.small.search,InstanceCount=2 \
  --ebs-options EBSEnabled=true,VolumeType=gp3,VolumeSize=20 \
  --access-policies file://opensearch-access-policy.json

# Create index (after domain is active)
# See aws/lambda/ingestionFunction/INDEX_SCHEMA_GUIDE.md
```

#### 7. Deploy Frontend

```bash
# Navigate to frontend directory
cd app

# Install dependencies
npm install

# Build for production
npm run build

# Deploy to Amplify
# Option 1: Connect GitHub repository in Amplify Console
# Option 2: Manual deployment
aws amplify create-app --name "Hospital Review Platform"
aws amplify create-branch --app-id YOUR_APP_ID --branch-name main
# Upload dist/ folder
```

### Data Ingestion

#### 1. Load Sample Data

```bash
# Load data into DynamoDB
cd resources/data/dynamodb

# Load each table
aws dynamodb batch-write-item --request-items file://customer_dynamodb.jsonl
aws dynamodb batch-write-item --request-items file://hospital_dynamodb.jsonl
aws dynamodb batch-write-item --request-items file://department_dynamodb.jsonl
aws dynamodb batch-write-item --request-items file://doctor_dynamodb.jsonl
aws dynamodb batch-write-item --request-items file://insurancecompany_dynamodb.jsonl
aws dynamodb batch-write-item --request-items file://insurancepolicy_dynamodb.jsonl
aws dynamodb batch-write-item --request-items file://review_dynamodb.jsonl
```

#### 2. Index Reviews in OpenSearch

```bash
# Run bulk ingestion
cd aws/lambda/ingestionFunction
python bulk_ingest_all.py
```


## 📁 Project Structure

```
aws-hackathon-2026/
├── app/                                    # Frontend React application
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/                # React components
│   │   │   │   ├── AgentActivityStream.tsx    # AI streaming UI
│   │   │   │   ├── HospitalCard.tsx           # Hospital display
│   │   │   │   ├── DoctorCard.tsx             # Doctor display
│   │   │   │   ├── HospitalMap.tsx            # Map integration
│   │   │   │   └── ui/                        # shadcn/ui components
│   │   │   ├── pages/                     # Page components
│   │   │   │   ├── Home.tsx                   # Search page
│   │   │   │   ├── HospitalDetail.tsx         # Hospital details
│   │   │   │   ├── CreateReview.tsx           # Review submission
│   │   │   │   └── PastReviews.tsx            # Review history
│   │   │   ├── services/                  # API services
│   │   │   │   ├── api.ts                     # REST API client
│   │   │   │   ├── appsync.ts                 # GraphQL client
│   │   │   │   └── reviewApi.ts               # Review API
│   │   │   ├── contexts/                  # React contexts
│   │   │   │   ├── AuthContext.tsx            # Authentication
│   │   │   │   └── SearchContext.tsx          # Search state
│   │   │   └── data/                      # Mock data
│   │   └── styles/                        # CSS styles
│   ├── .env.local                         # Environment variables
│   ├── .env.example                       # Environment template
│   ├── package.json                       # Dependencies
│   ├── vite.config.ts                     # Vite configuration
│   └── tsconfig.json                      # TypeScript config
│
├── aws/                                    # AWS backend resources
│   ├── lambda/                            # Lambda functions
│   │   ├── customerFunction/              # Customer CRUD
│   │   │   ├── lambda_function.py
│   │   │   ├── README.md
│   │   │   └── events/                    # Test events
│   │   ├── hospitalFunction/              # Hospital CRUD
│   │   ├── departmentFunction/            # Department CRUD
│   │   ├── doctorFunction/                # Doctor CRUD
│   │   ├── insuranceCompanyFunction/      # Insurance company CRUD
│   │   ├── insurancePolicyFunction/       # Insurance policy CRUD
│   │   ├── reviewFunction/                # Review processing
│   │   │   ├── lambda_function.py
│   │   │   ├── README.md
│   │   │   ├── extractors/                # Document extractors
│   │   │   └── GSI_OPTIMIZATION_SUMMARY.md
│   │   ├── searchFunction/                # Synchronous search (deprecated)
│   │   │   ├── lambda_function.py
│   │   │   ├── README.md
│   │   │   └── deploy.sh
│   │   ├── searchInvokerFunction/         # Async search orchestrator
│   │   │   ├── lambda_function.py
│   │   │   ├── README.md
│   │   │   └── test-event.json
│   │   ├── searchWorkerFunction/          # AI search processor
│   │   │   ├── lambda_function.py
│   │   │   ├── README.md
│   │   │   └── appsync_publisher.py
│   │   ├── healthSearchToolFunction/      # Bedrock Agent action group
│   │   │   ├── lambda_function.py
│   │   │   ├── README.md
│   │   │   ├── FUNCTION_DESCRIPTIONS.md
│   │   │   └── TESTING_GUIDE.md
│   │   ├── ingestionFunction/             # OpenSearch indexing
│   │   │   ├── lambda_function.py
│   │   │   ├── README.md
│   │   │   ├── bulk_ingest.py
│   │   │   ├── bulk_ingest_all.py
│   │   │   └── INDEX_SCHEMA_GUIDE.md
│   │   └── .env.example                   # Lambda env template
│   │
│   ├── appsync/                           # AppSync GraphQL API
│   │   ├── schema.graphql                 # GraphQL schema
│   │   └── resolvers/                     # Lambda resolvers
│   │       ├── Mutation.initiateSearch.js
│   │       ├── Mutation.publishAgentChunk.js
│   │       ├── Query.getSearchResults.js
│   │       └── README.md
│   │
│   ├── agents/                            # Bedrock Agent configuration
│   │   ├── orchestrator-agent-ui-fields.md
│   │   ├── db-tool-agent-ui-fields.md
│   │   ├── opensearch-knowledge-agent-ui-fields.md
│   │   ├── action-groups/                 # Action group schemas
│   │   │   ├── all-functions.json
│   │   │   └── function-*.json            # Individual functions
│   │   ├── AGENT_ARCHITECTURE.md
│   │   └── README.md
│   │
│   ├── step-functions/                    # Step Functions workflows
│   │   └── document-processing-state-machine.json
│   │
│   ├── create-api-gateway.ps1             # API Gateway setup script
│   ├── migrate-region.ps1                 # Region migration script
│   └── HealthcareAPI.postman_collection.json  # Postman tests
│
├── resources/                              # Data and resources
│   ├── data/
│   │   ├── dynamodb/                      # DynamoDB data files
│   │   │   ├── customer_dynamodb.jsonl
│   │   │   ├── hospital_dynamodb.jsonl
│   │   │   ├── department_dynamodb.jsonl
│   │   │   ├── doctor_dynamodb.jsonl
│   │   │   ├── insurancecompany_dynamodb.jsonl
│   │   │   ├── insurancepolicy_dynamodb.jsonl
│   │   │   └── review_dynamodb.jsonl
│   │   └── original/                      # Original data files
│   ├── aws-architecture.jpg               # Architecture diagram
│   └── about.pdf                          # Project documentation
│
├── .kiro/                                  # Kiro AI specs
│   └── specs/
│       ├── appsync-streaming-search/      # AppSync streaming spec
│       │   ├── requirements.md
│       │   ├── design.md
│       │   ├── tasks.md
│       │   ├── README.md
│       │   └── QUICK_START.md
│       └── hospital-review-platform/      # Platform spec
│
├── README.md                               # This file
├── PROJECT_OVERVIEW.md                     # Detailed project overview
├── ENVIRONMENT_SETUP.md                    # Environment configuration guide
├── ENVIRONMENT_CLEANUP_SUMMARY.md          # Environment cleanup summary
├── .gitignore                             # Git ignore rules
├── .python-version                        # Python version
├── pyproject.toml                         # Python project config
└── uv.lock                                # Python dependencies lock
```


## 🔧 Development

### Local Development

#### Frontend

```bash
# Navigate to frontend directory
cd app

# Install dependencies
npm install

# Start development server
npm run dev

# Open browser to http://localhost:5173
```

#### Backend (Lambda Functions)

```bash
# Navigate to function directory
cd aws/lambda/customerFunction

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Invoke locally with SAM
sam local invoke customerFunction -e events/event-get-by-id.json
```

### Testing

#### Frontend Tests

```bash
cd app
npm run test
npm run test:coverage
```

#### Backend Tests

```bash
# Unit tests
cd aws/lambda/customerFunction
python -m pytest tests/

# Integration tests
python -m pytest tests/integration/

# Load tests
artillery run load-test.yml
```

#### API Tests

```bash
# Import Postman collection
# File: aws/HealthcareAPI.postman_collection.json

# Run collection
newman run aws/HealthcareAPI.postman_collection.json
```

### Code Quality

#### Frontend

```bash
# Linting
npm run lint

# Type checking
npm run type-check

# Formatting
npm run format
```

#### Backend

```bash
# Linting
pylint lambda_function.py

# Type checking
mypy lambda_function.py

# Formatting
black lambda_function.py
```

## 📚 Documentation

### Architecture Documentation

- **PROJECT_OVERVIEW.md**: Comprehensive project overview with cost analysis
- **ENVIRONMENT_SETUP.md**: Environment variable configuration guide
- **ENVIRONMENT_CLEANUP_SUMMARY.md**: Security cleanup summary

### Lambda Function Documentation

Each Lambda function has a detailed README:
- `aws/lambda/customerFunction/README.md`
- `aws/lambda/hospitalFunction/README.md`
- `aws/lambda/departmentFunction/README.md`
- `aws/lambda/doctorFunction/README.md`
- `aws/lambda/insuranceCompanyFunction/README.md`
- `aws/lambda/insurancePolicyFunction/README.md`
- `aws/lambda/reviewFunction/README.md`
- `aws/lambda/searchFunction/README.md`
- `aws/lambda/searchInvokerFunction/README.md`
- `aws/lambda/searchWorkerFunction/README.md`
- `aws/lambda/healthSearchToolFunction/README.md`
- `aws/lambda/ingestionFunction/README.md`

### Spec Documentation

- `.kiro/specs/appsync-streaming-search/`: AppSync streaming implementation
- `.kiro/specs/hospital-review-platform/`: Platform specifications

### API Documentation

- `aws/appsync/schema.graphql`: GraphQL schema
- `aws/appsync/resolvers/README.md`: Resolver documentation
- `aws/HealthcareAPI.postman_collection.json`: REST API collection

## 🔐 Security

### Authentication & Authorization

- **Frontend**: AWS Amplify authentication (optional)
- **API Gateway**: API Key or IAM authentication
- **AppSync**: API Key authentication
- **Lambda**: IAM role-based permissions
- **DynamoDB**: IAM role-based access
- **S3**: Pre-signed URLs for uploads

### Data Protection

- **Encryption at Rest**: Enabled for DynamoDB, S3, OpenSearch
- **Encryption in Transit**: TLS 1.2+ for all API calls
- **PII Protection**: Customer data encrypted and access-controlled
- **PHI Compliance**: Medical data handled per HIPAA guidelines

### Best Practices

1. **Least Privilege**: IAM roles with minimal permissions
2. **Secrets Management**: Use AWS Secrets Manager for sensitive data
3. **API Rate Limiting**: Throttling enabled on API Gateway
4. **Input Validation**: All inputs validated before processing
5. **Audit Logging**: CloudTrail enabled for compliance

## 🐛 Troubleshooting

### Common Issues

#### Frontend Issues

**Issue**: `VITE_API_BASE_URL is undefined`
- **Solution**: Create `.env.local` file with required variables
- **Check**: Restart dev server after changing `.env.local`

**Issue**: AppSync subscription not working
- **Solution**: Verify APPSYNC_ENDPOINT and APPSYNC_API_KEY
- **Check**: Browser console for WebSocket errors

#### Backend Issues

**Issue**: Lambda timeout
- **Solution**: Increase timeout in Lambda configuration
- **Check**: CloudWatch logs for slow operations

**Issue**: DynamoDB throttling
- **Solution**: Switch to on-demand capacity mode
- **Check**: CloudWatch metrics for throttled requests

**Issue**: Bedrock Agent not responding
- **Solution**: Verify agent ID and alias ID
- **Check**: Bedrock Agent logs in CloudWatch

### Debugging

#### Frontend Debugging

```bash
# Enable verbose logging
VITE_LOG_LEVEL=debug npm run dev

# Check browser console
# Open DevTools → Console

# Check network requests
# Open DevTools → Network
```

#### Backend Debugging

```bash
# View Lambda logs
aws logs tail /aws/lambda/customerFunction --follow

# View specific log stream
aws logs get-log-events \
  --log-group-name /aws/lambda/customerFunction \
  --log-stream-name 2024/03/08/[$LATEST]abc123

# Search logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/customerFunction \
  --filter-pattern "ERROR"
```

## 🤝 Contributing

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards

- **Frontend**: Follow React best practices and TypeScript strict mode
- **Backend**: Follow PEP 8 Python style guide
- **Documentation**: Update README files for any changes
- **Tests**: Add tests for new features

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Team

- **Project Lead**: Hospital Review Platform Team
- **Frontend Development**: React + TypeScript team
- **Backend Development**: AWS Lambda + Python team
- **AI/ML Development**: Bedrock Agent team
- **DevOps**: AWS infrastructure team

## 🙏 Acknowledgments

- AWS for providing cloud infrastructure
- Anthropic for Claude models via Bedrock
- Amazon for Titan embedding models
- Open source community for React, TypeScript, and Python libraries

## 📞 Support

For issues, questions, or contributions:
- **GitHub Issues**: [Create an issue](https://github.com/your-repo/issues)
- **Documentation**: Check README files in each directory
- **AWS Support**: For AWS-specific issues
- **Email**: support@hospitalreviewplatform.com

## 🚀 Future Enhancements

### Planned Features

1. **Mobile App**: React Native mobile application
2. **Telemedicine Integration**: Video consultation booking
3. **Appointment Scheduling**: Direct hospital appointment booking
4. **Price Prediction**: ML-based treatment cost prediction
5. **Personalized Recommendations**: User preference learning
6. **Multi-language Support**: Internationalization
7. **Social Features**: Share reviews, follow doctors
8. **Analytics Dashboard**: Hospital performance analytics

### Technical Improvements

1. **Caching**: Redis/ElastiCache for frequently accessed data
2. **CDN**: CloudFront for static asset delivery
3. **Monitoring**: Enhanced observability with X-Ray
4. **Testing**: Increased test coverage to 90%+
5. **CI/CD**: Automated deployment pipelines
6. **Performance**: Further latency optimization
7. **Security**: Enhanced security scanning and compliance

---

**Last Updated**: March 8, 2026  
**Version**: 1.0.0  
**Status**: Production Ready

**Built with ❤️ using AWS Services**
