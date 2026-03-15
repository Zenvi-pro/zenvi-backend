import React from 'react';
import { Composition } from 'remotion';
import { ProductLaunchVideo, ProductLaunchVideoProps } from './ProductLaunchVideo';

const DEFAULT_FPS = 30;
const DEFAULT_DURATION = 30 * DEFAULT_FPS;

export const Root: React.FC = () => {
  return (
    <Composition<ProductLaunchVideoProps>
      id="ProductLaunchVideo"
      component={ProductLaunchVideo}
      durationInFrames={DEFAULT_DURATION}
      fps={DEFAULT_FPS}
      width={1920}
      height={1080}
      defaultProps={{
        repoData: {
          owner: 'example',
          repo: 'project',
          name: 'My Project',
          description: 'An amazing open-source project',
          stars: 2500,
          forks: 340,
          language: 'TypeScript',
          topics: ['open-source', 'developer-tools', 'productivity'],
          homepage: 'https://example.com',
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
  );
};
