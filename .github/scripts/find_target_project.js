// .github/scripts/find_target_project.js

/**
 * Find target projects from changed files (or explicit input).
 *
 * Inputs are passed via environment variables so this module can be loaded by
 * actions/github-script with `require`:
 *   - TARGET_PROJECTS: comma separated project paths. If set, used as-is.
 *   - REQUIRED_FILES:  comma separated file names that identify a project.
 *   - CHANGED_FILES:   JSON array of changed file/directory paths.
 *
 * @param {object} params
 * @param {import('@actions/core')} params.core
 */
module.exports = async ({ core }) => {
  const fs = require('node:fs');

  // If target_projects input is provided, use it as-is.
  const dispatchInput = (process.env.TARGET_PROJECTS ?? '').trim();
  if (dispatchInput !== '') {
    const projects = dispatchInput.split(',').map(path => path.trim());
    core.setOutput('projects', JSON.stringify(projects));
    return;
  }

  // Otherwise, derive projects from the changed files.
  // CHANGED_FILES may be an empty string when nothing changed, so guard JSON.parse.
  const changedPaths = JSON.parse((process.env.CHANGED_FILES ?? '').trim() || '[]');
  // convert ['hoge/fuga', 'foo/zoo'] => ['hoge', 'hoge/fuga', 'foo', 'foo/zoo']
  const set = new Set();
  changedPaths.forEach(path => {
    const segments = path.split('/');
    let current = '';
    segments.forEach((segment, index) => {
      current = index === 0 ? segment : `${current}/${segment}`;
      set.add(current);
    });
  });
  const changedDirectories = Array.from(set);

  const requiredFiles = (process.env.REQUIRED_FILES ?? '')
    .split(',')
    .map(path => path.trim());

  // Keep only directories that contain all required files.
  const projects = changedDirectories.filter(path => {
    if (fs.existsSync(path) && fs.statSync(path).isDirectory()) {
      return requiredFiles.every(file => fs.existsSync(`${path}/${file}`));
    }
    return false;
  });
  core.setOutput('projects', JSON.stringify(projects));
};
