export type RuntimeConfig = {
  python: string;
  project: string;
  version: string;
  bridgeModule: string;
  cliModule: string;
  env: NodeJS.ProcessEnv;
};

export function readRuntimeConfig(): RuntimeConfig {
  const python = process.env.SADQUANT_TUI_PYTHON;
  if (!python) {
    throw new Error('SADQUANT_TUI_PYTHON is not set.');
  }
  return {
    python,
    project: process.env.SADQUANT_TUI_PROJECT ?? process.cwd(),
    version: process.env.SADQUANT_TUI_VERSION ?? 'dev',
    bridgeModule: process.env.SADQUANT_TUI_BRIDGE_MODULE ?? 'sadquant.tui_bridge',
    cliModule: process.env.SADQUANT_TUI_CLI_MODULE ?? 'sadquant.cli',
    env: process.env
  };
}
