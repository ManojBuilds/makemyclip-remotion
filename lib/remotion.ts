import {
  createSandbox,
  addBundleToSandbox,
  renderMediaOnVercel,
} from "@remotion/vercel"
import { execSync } from "child_process"
import { tmpdir } from "os"
import path from "path"

export { createSandbox, addBundleToSandbox, renderMediaOnVercel }

const BUNDLE_DIR = path.join(tmpdir(), "remotion-bundle")

/**
 * Bundles the Remotion project using the CLI (like the official template).
 * This respects remotion.config.ts for webpack overrides (e.g. @/ alias).
 * Returns the relative bundle directory path for use with addBundleToSandbox.
 */
export function bundleRemotionProject(): string {
  try {
    execSync(
      `npx remotion bundle remotion-project/index.ts --out-dir ${BUNDLE_DIR}`,
      { cwd: process.cwd(), stdio: "inherit" }
    )
  } catch (e) {
    const stderr = (e as { stderr?: Buffer }).stderr?.toString() ?? ""
    throw new Error(`Remotion bundle failed: ${stderr}`)
  }
  return BUNDLE_DIR
}
