/**
 * Resolver for getSearchResults query
 * Fetches search results from DynamoDB SearchResults table
 * 
 * @param {import('@aws-appsync/utils').Context} ctx the context
 * @returns {*} the request
 */
export function request(ctx) {
    const { searchId } = ctx.arguments;
    
    return {
        operation: "GetItem",
        key: util.dynamodb.toMapValues({ searchId }),
        consistentRead: true
    };
}

/**
 * Returns the resolver result
 * 
 * @param {import('@aws-appsync/utils').Context} ctx the context
 * @returns {*} the result
 */
export function response(ctx) {
    if (ctx.error) {
        util.error(ctx.error.message, ctx.error.type);
    }
    
    const item = ctx.result;
    
    if (!item) {
        return null;
    }
    
    // Log for debugging
    console.log("DynamoDB item keys:", Object.keys(item));
    console.log("llmResponse type:", typeof item.llmResponse);
    console.log("llmResponse value:", JSON.stringify(item.llmResponse));
    
    // Current structure: { searchId, status, llmResponse: { aiSummary, hospitals }, error, updatedAt, ttl }
    // llmResponse might be a Map type from DynamoDB
    const llmResponse = item.llmResponse;
    
    return {
        searchId: item.searchId,
        status: item.status || "processing",
        results: llmResponse ? {
            aiSummary: llmResponse.aiSummary || llmResponse.get?.("aiSummary") || "Search completed successfully",
            hospitals: llmResponse.hospitals || llmResponse.get?.("hospitals") || []
        } : null,
        error: item.error || null
    };
}
