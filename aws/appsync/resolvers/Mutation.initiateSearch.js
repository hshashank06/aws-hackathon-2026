/**
 * Resolver for initiateSearch mutation
 * Invokes InvokerLambda with the provided arguments
 * 
 * @param {import('@aws-appsync/utils').Context} ctx the context
 * @returns {*} the request
 */
export function request(ctx) {
    return {
        operation: "Invoke",
        payload: {
            arguments: ctx.arguments
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
    // Return the Lambda response
    // Expected format: { searchId: string, status: string }
    return ctx.result;
}
