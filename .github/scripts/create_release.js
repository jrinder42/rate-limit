// Uses GitHub's API to create the release and wait for result.
// We use a JS script since github CLI doesn't provide a way to wait for the release's creation and returns immediately.
// Inspired by https://github.com/vllm-project/vllm/blob/main/.github/workflows/scripts/create_release.js

module.exports = async (github, context, core) => {
	try {
		const response = await github.rest.repos.createRelease({
			draft: process.env.IS_DRAFT === 'true',
			prerelease: process.env.IS_PRERELEASE === 'true',
			generate_release_notes: true,
			name: process.env.RELEASE_TAG,
			owner: context.repo.owner,
			repo: context.repo.repo,
			tag_name: process.env.RELEASE_TAG,
		});

		core.setOutput('upload_url', response.data.upload_url);
	} catch (error) {
		core.setFailed(error.message);
	}
}