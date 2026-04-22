import path from 'node:path'
import fs from 'node:fs/promises'

export async function withGracefulShutdown(
  fn: (signal: AbortSignal) => Promise<void>,
  options?: { timeoutMs?: number },
): Promise<void> {
  const controller = new AbortController()
  const timeoutMs = options?.timeoutMs ?? 30_000

  const shutdown = async () => {
    if (controller.signal.aborted) {
      console.error(`${new Date().toISOString()} Forcefully exiting...`)
      process.exit(1)
    }

    console.log(`${new Date().toISOString()} Gracefully shutting down...`)
    controller.abort()

    setTimeout(() => {
      console.error(
        `${new Date().toISOString()} Shutdown timed out, exiting...`,
      )
      process.exit(1)
    }, timeoutMs)
  }

  using disposer = new DisposableStack()

  process.on('SIGINT', shutdown)
  disposer.defer(() => process.off('SIGINT', shutdown))

  process.on('SIGTERM', shutdown)
  disposer.defer(() => process.off('SIGTERM', shutdown))

  await fn(controller.signal)
}

export async function linkFile(
  srcDir: string,
  destDir: string,
  fileName: string,
) {
  const src = path.resolve(srcDir, fileName)
  await fs.access(src)

  const absDestDir = path.resolve(destDir)
  await fs.mkdir(absDestDir, { recursive: true })
  const dest = path.join(absDestDir, fileName)

  const stat = await fs.lstat(dest).catch(() => null)
  if (stat) {
    if (stat.isSymbolicLink()) {
      await fs.unlink(dest)
    } else if (stat.isFile()) {
      await fs.rm(`${dest}.bak`, { force: true })
      await fs.rename(dest, `${dest}.bak`)
    } else {
      throw new Error(`Expected ${dest} to be a file or symlink`)
    }
  }

  const relSrc = path.relative(absDestDir, src)
  await fs.symlink(relSrc, dest)
}

export async function createPathMap() {
  const repoRoot = path.resolve(import.meta.dirname, '../../..')
  const hasPackageJson = await fs
    .access(path.join(repoRoot, 'package.json'))
    .then(() => true)
    .catch(() => false)
  if (!hasPackageJson) {
    throw new Error(`Expected to find package.json in repo root at ${repoRoot}`)
  }

  return { repoRoot }
}

export type PathMap = Awaited<ReturnType<typeof createPathMap>>
