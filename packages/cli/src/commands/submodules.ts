import { Command } from 'commander'
import { exec } from 'node:child_process'
import { promisify } from 'node:util'
import { withGracefulShutdown } from '../common.ts'

const execAsync = promisify(exec)

export const submodules = new Command('submodules').action(() =>
  withGracefulShutdown(async signal => {
    console.log('Updating git submodules...')

    await execAsync('git submodule update --init --recursive', { signal })
    console.log('Git submodules updated successfully!')
  }),
)
