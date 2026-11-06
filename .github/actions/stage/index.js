// Adapted from ungoogled-chromium-windows (BSD-3-Clause).
//
// One build stage: restore the build tree a previous stage left, run
// `build.py --ci` until it finishes or times out (exit 124), then upload either
// the packages or the build tree for the next stage.
//
// A job may run 6 hours. Ninja stops NINJA_MINUTES after this script starts,
// however long the steps before it took (unpacking the tarball and patching in
// the first stage, the build tree in later ones), which leaves time to pack and
// upload the tree. The standard Windows runner has 4 cores and 16 GB of RAM.
import * as core from '@actions/core';
import * as io from '@actions/io';
import * as exec from '@actions/exec';
import { DefaultArtifactClient } from '@actions/artifact';
import * as glob from '@actions/glob';

const BUILD_TIMEOUT_EXIT_CODE = 124;
const NINJA_MINUTES = 280;
const NINJA_JOBS = '3';
const ROOT = 'C:\\a';
const BUILD = `${ROOT}\\ungoogled-chromium-windows\\build`;

async function upload(artifact, name, files, rootDirectory) {
    for (let i = 0; i < 5; ++i) {
        try {
            await artifact.deleteArtifact(name);
        } catch (e) {
            // No artifact yet.
        }
        try {
            await artifact.uploadArtifact(name, files, rootDirectory,
                {retentionDays: 4, compressionLevel: 0});
            return;
        } catch (e) {
            console.error(`Upload artifact failed: ${e}`);
            await new Promise(r => setTimeout(r, 10000));
        }
    }
    throw new Error(`Could not upload ${name}`);
}

async function run() {
    const deadline = Date.now() / 1000 + NINJA_MINUTES * 60;
    process.on('SIGINT', function() {});
    const finished = core.getBooleanInput('finished', {required: true});
    const fromArtifact = core.getBooleanInput('from_artifact', {required: true});
    const arm = core.getBooleanInput('arm', {required: false});
    console.log(`finished: ${finished}, artifact: ${fromArtifact}`);
    if (finished) {
        core.setOutput('finished', true);
        return;
    }

    const artifact = new DefaultArtifactClient();
    const treeArtifact = arm ? 'build-tree-arm64' : 'build-tree-x64';

    if (fromArtifact) {
        await exec.exec(process.execPath, [`${import.meta.dirname}\\download.js`, treeArtifact, BUILD]);
        await exec.exec('7z', ['x', `${BUILD}\\artifacts.zip`, `-o${BUILD}`, '-y']);
        await io.rmRF(`${BUILD}\\artifacts.zip`);
    }

    const archArgs = arm ? ['--arm'] : [];
    const args = ['build.py', '--ci', '-j', NINJA_JOBS, ...archArgs];
    await exec.exec('python', ['-m', 'pip', 'install', 'httplib2==0.22.0', 'clang==21.1.7'], {
        cwd: ROOT,
        ignoreReturnCode: true
    });
    const retCode = await exec.exec('python', args, {
        cwd: ROOT,
        ignoreReturnCode: true,
        env: {...process.env, ARCOMIUM_CI_DEADLINE: String(Math.floor(deadline))}
    });

    if (retCode === 0) {
        // Release packages are built with PGO, or not at all.
        await exec.exec('python', ['build.py', '--pgo-check', ...archArgs], {cwd: ROOT});
        core.setOutput('finished', true);
        const globber = await glob.create(`${BUILD}\\ungoogled-chromium*`, {matchDirectories: false});
        await upload(artifact, arm ? 'packages-arm64' : 'packages-x64', await globber.glob(), BUILD);
    } else if (retCode === BUILD_TIMEOUT_EXIT_CODE) {
        await new Promise(r => setTimeout(r, 5000));
        // 7-Zip exits 1 for warnings (a file it could not open), 2 and up for
        // errors: a broken build tree must not go on to the next stage.
        const zipCode = await exec.exec(
            '7z', ['a', '-tzip', `${ROOT}\\artifacts.zip`, `${BUILD}\\src`, '-mx=3', '-mtc=on'],
            {ignoreReturnCode: true});
        if (zipCode > 1) {
            throw new Error(`7-Zip failed with exit code ${zipCode}`);
        }
        await upload(artifact, treeArtifact, [`${ROOT}\\artifacts.zip`], ROOT);
        core.setOutput('finished', false);
    } else {
        throw new Error(`Build failed with exit code ${retCode}`);
    }
}

run().catch(err => core.setFailed(err.message));
