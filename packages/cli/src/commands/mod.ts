import { Command } from 'commander'
import { exec } from 'node:child_process'
import { promisify } from 'node:util'
import { createPathMap, linkFile, withGracefulShutdown } from '../common.ts'
import os from 'node:os'
import path from 'node:path'
import fs from 'node:fs/promises'

const execAsync = promisify(exec)

export const mod = new Command('mod').action(() =>
  withGracefulShutdown(async signal => {
    console.log('Building and linking mod...')

    const { repoRoot } = await createPathMap()
    const workDir = path.join(repoRoot, '.work')
    await fs.mkdir(workDir, { recursive: true })

    const steamappsDir = path.join(
      os.homedir(),
      'Library',
      'Application Support',
      'Steam',
      'steamapps',
    )
    const resourcesDir = path.join(
      steamappsDir,
      'common',
      'SlayTheSpire',
      'SlayTheSpire.app',
      'Contents',
      'Resources',
    )
    const desktopJarPath = path.join(resourcesDir, 'desktop-1.0.jar')
    const modDir = path.join(resourcesDir, 'mods')
    const workshopDir = path.join(steamappsDir, 'workshop', 'content', '646570')
    const modTheSpireJarPath = path.join(
      workshopDir,
      '1605060445',
      'ModTheSpire.jar',
    )
    const baseModJarPath = path.join(workshopDir, '1605833019', 'BaseMod.jar')
    const buildJarPath = path.join(workDir, 'CommunicationMod.jar')
    const communicationModDir = path.join(
      repoRoot,
      'external',
      'CommunicationMod',
    )
    const javaHomeDir = path.join(
      os.homedir(),
      '.sdkman',
      'candidates',
      'java',
      '8.0.482-zulu',
    )

    const env: NodeJS.ProcessEnv = { ...process.env, JAVA_HOME: javaHomeDir }
    const { PATH } = process.env
    if (PATH) {
      env.PATH = `${path.join(javaHomeDir, 'bin')}${path.delimiter}${PATH}`
    } else {
      env.PATH = path.join(javaHomeDir, 'bin')
    }

    await execAsync(
      [
        'mvn',
        `-Dcommunicationmod.desktop.jar="${desktopJarPath}"`,
        `-Dcommunicationmod.modthespire.jar="${modTheSpireJarPath}"`,
        `-Dcommunicationmod.basemod.jar="${baseModJarPath}"`,
        `-Dcommunicationmod.build.jar="${buildJarPath}"`,
        'clean',
        'package',
      ].join(' '),
      { signal, cwd: communicationModDir, env },
    )

    await fs.mkdir(modDir, { recursive: true })
    await linkFile(workDir, modDir, 'CommunicationMod.jar')

    console.log('Mod built and linked successfully')
  }),
)
