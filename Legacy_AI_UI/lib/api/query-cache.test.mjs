import {
  queryKey, fetchQuery, readQuery, isFresh, subscribeQuery,
  mutateQuery, invalidateQueries, clearQueryCache, hasBeenAttempted,
} from './query-cache.ts'

let pass = 0, fail = 0
const ok = (cond, label) => { cond ? (pass++, console.log('  PASS', label)) : (fail++, console.log('  FAIL', label)) }

ok(queryKey('a', 1, undefined) === queryKey('a', 1, null), 'undefined and null collapse to the same key')
ok(queryKey('t', { b: 2, a: 1 }) === queryKey('t', { a: 1, b: 2 }), 'object param key order does not matter')
ok(queryKey('t', 1) !== queryKey('t', 2), 'different params -> different keys')

let calls = 0
const fetcher = () => { calls++; return new Promise(r => setTimeout(() => r({ n: calls }), 30)) }
const key = queryKey('traces:recent', 100, undefined)
const results = await Promise.all([1, 2, 3, 4].map(() => fetchQuery(key, fetcher)))
ok(calls === 1, `4 concurrent callers produced ${calls} request (expected 1)`)
ok(results.every(r => r === results[0]), 'all callers got the same object')

ok(isFresh(key, 5000), 'entry reports fresh inside the TTL')
ok(!isFresh(key, 0), 'entry reports stale with a zero TTL')
ok(readQuery(key).data === results[0], 'readQuery returns the cached value')
ok(readQuery(key).loading === false && readQuery(key).validating === false, 'settled entry is neither loading nor validating')
ok(readQuery(key) === readQuery(key), 'snapshot identity is stable between reads')

let notified = 0
const unsub = subscribeQuery(key, () => notified++)
mutateQuery(key, prev => ({ ...prev, n: 99 }))
ok(notified === 1, 'mutate notifies subscribers')
ok(readQuery(key).data.n === 99, 'mutate rewrites the cached value')
invalidateQueries('traces:recent')
ok(notified === 2, 'invalidate notifies subscribers')
ok(!isFresh(key, 5000), 'invalidate marks the entry stale')
unsub()
mutateQuery(key, p => p)
ok(notified === 2, 'unsubscribed listener is not called')

const badKey = queryKey('bad')
let threw = false
try { await fetchQuery(badKey, () => Promise.reject(new Error('boom'))) } catch { threw = true }
ok(threw, 'fetchQuery rethrows so callers can react')
ok(readQuery(badKey).error === 'boom', 'error message is recorded on the entry')
ok(readQuery(badKey).loading === false, 'a failed entry is not stuck loading')
ok(hasBeenAttempted(badKey), 'a failed entry counts as attempted')

const retried = await fetchQuery(badKey, () => Promise.resolve('recovered'))
ok(retried === 'recovered' && readQuery(badKey).error === null, 'a successful retry clears the error')

clearQueryCache()
ok(readQuery(key).data === undefined, 'clearQueryCache empties the cache')

console.log(`\n${pass} passed, ${fail} failed`)
process.exit(fail ? 1 : 0)
