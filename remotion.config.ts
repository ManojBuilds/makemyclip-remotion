import { Config } from "@remotion/cli/config"
import path from "path"

Config.overrideWebpackConfig((config) => ({
  ...config,
  resolve: {
    ...config.resolve,
    alias: {
      ...(config.resolve?.alias || {}),
      "@": path.resolve(process.cwd()),
    },
  },
}))
