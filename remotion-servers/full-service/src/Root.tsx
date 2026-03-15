import React from 'react';
import { Composition } from 'remotion';
import { RepoVideo, RepoVideoProps } from './RepoVideo';
import { SonarVideo, SonarVideoProps } from './SonarVideo';

const DEFAULT_FPS = 30;
const DEFAULT_DURATION = 30 * DEFAULT_FPS; // 30 seconds

export const Root: React.FC = () => {
  return (
    <>
      <Composition<RepoVideoProps>
        id="RepoVideo"
        component={RepoVideo}
        durationInFrames={DEFAULT_DURATION}
        fps={DEFAULT_FPS}
        width={1920}
        height={1080}
        defaultProps={{
          repoUrl: 'https://github.com/example/repo',
          repoData: {
            owner: 'example',
            repo: 'repo',
            name: 'Example Repo',
            description: 'An example repository',
            stars: 1000,
            forks: 200,
            language: 'TypeScript',
            topics: ['open-source', 'developer-tools'],
            homepage: '',
            readme: '',
          },
          theme: {
            bg: '#0f0f1a',
            accent: '#4f8ef7',
            text: '#ffffff',
            sub: '#a0aec0',
          },
          durationInFrames: DEFAULT_DURATION,
        }}
      />

      <Composition<SonarVideoProps>
        id="SonarVideo"
        component={SonarVideo}
        durationInFrames={DEFAULT_DURATION}
        fps={DEFAULT_FPS}
        width={1920}
        height={1080}
        defaultProps={{
          researchData: {
            topic: 'Example Topic',
            summary: 'A summary of research findings.',
            keyPoints: ['Point one', 'Point two', 'Point three'],
            citations: [],
          },
          theme: {
            bg: '#0f0f1a',
            accent: '#4f8ef7',
            text: '#ffffff',
            sub: '#a0aec0',
          },
          durationInFrames: DEFAULT_DURATION,
        }}
      />
    </>
  );
};
