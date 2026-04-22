import { program } from 'commander'
import { submodules } from './commands/submodules.ts'
import { mod } from './commands/mod.ts'

await program.name('cli').addCommand(submodules).addCommand(mod).parseAsync()
