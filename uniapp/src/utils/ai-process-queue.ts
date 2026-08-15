export async function runSequentially<T, TResult>(
  items: readonly T[],
  worker: (item: T) => Promise<TResult>,
): Promise<PromiseSettledResult<TResult>[]> {
  const results: PromiseSettledResult<TResult>[] = []

  for (const item of items) {
    try {
      results.push({ status: 'fulfilled', value: await worker(item) })
    } catch (reason) {
      results.push({ status: 'rejected', reason })
    }
  }

  return results
}
