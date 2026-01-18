// .github/scripts/release-helper.js

/**
 * @param {object} params
 * @param {import('@octokit/rest').Octokit} params.github
 * @param {import('@actions/github/lib/context').Context} params.context
 * @param {import('@actions/core')} params.core
 */
module.exports = async ({ github, context, core }) => {
  // ここにロジックを書く
  core.info("外部スクリプトを開始します");
  const fs = require('node:fs');
  // If target_projects input is provided, use it
  let dispatch_inputs = "${{ inputs.target_projects }}";
  if (dispatch_inputs !== "") {
    dispatch_inputs = dispatch_inputs.split(',').map(path => path.trim());
    core.setOutput('projects', JSON.stringify(dispatch_inputs));
  } else { // If no input is provided, get directories from changed files
    const changed_paths = JSON.parse(${{ toJSON(steps.changed-files.outputs.all_changed_and_modified_files) }});
    // convert ['hoge/fuga', 'foo/zoo'] => ['hoge', 'hoge/fuga', 'foo', 'foo/zoo']
    const set = new Set();
    changed_paths.forEach(path => {
      const segments = path.split('/');
      let current = '';
      segments.forEach((segment, index) => {
        current = index === 0 ? segment : `${current}/${segment}`;
        set.add(current);
      });
    });
    const changed_directories = Array.from(set);
    const required_files = "${{ inputs.required_files }}".split(',').map(path => path.trim());
    // Filter out directories that contain required files.
    const projects = changed_directories.filter(path => {
      if (
        fs.statSync(path).isDirectory()
      ) {
        // Check if all required files exist in the directory
        const all_files_exist = required_files.every(file => fs.existsSync(`${path}/${file}`));
        if (all_files_exist) {
          return true;
        }
      }
      return false;
    });
    core.setOutput('projects', JSON.stringify(projects));
  }
  const { owner, repo } = context.repo;

  // 例: Issueを作成する
  await github.rest.issues.create({
    owner,
    repo,
    title: "Automated Issue via Script",
    body: "これは外部ファイルから作成されました。",
  });

  return "完了";
};
