const OPENAPI_URL = 'http://127.0.0.1:8000/openapi.json'
const MAX_ATTEMPTS = 30
const RETRY_DELAY_MS = 2000

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

let lastError = ''

for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
  try {
    const response = await fetch(OPENAPI_URL)
    if (response.ok) {
      console.log(`OpenAPI is ready: ${OPENAPI_URL}`)
      process.exit(0)
    }
    lastError = `HTTP ${response.status}`
  } catch (error) {
    lastError = error instanceof Error ? error.message : String(error)
  }

  if (attempt < MAX_ATTEMPTS) {
    await sleep(RETRY_DELAY_MS)
  }
}

console.error(
  `Backend did not serve ${OPENAPI_URL} after ${MAX_ATTEMPTS} attempts. Last error: ${lastError}`,
)
process.exit(1)
