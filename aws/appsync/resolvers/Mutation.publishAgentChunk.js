/**
 * Resolver for publishAgentChunk mutation
 * Uses NONE data source - just publishes to subscriptions
 * 
 * @param {import('@aws-appsync/utils').Context} ctx the context
 * @returns {*} the request
 */
export function request(ctx) {
    // NONE data source - return the payload with timestamp
    return {
        payload: {
            searchId: ctx.arguments.searchId,
            chunk: ctx.arguments.chunk,
            timestamp: util.time.nowISO8601()
        }
    };
}

/**
 * Returns the resolver result
 * 
 * @param {import('@aws-appsync/utils').Context} ctx the context
 * @returns {*} the result
 */
export function response(ctx) {
    // Return the payload from request
    return ctx.result;
}
