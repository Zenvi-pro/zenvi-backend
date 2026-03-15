import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Sequence,
  Easing,
} from 'remotion';
import type { Theme } from './RepoVideo';

export interface SonarResearchData {
  topic: string;
  summary: string;
  keyPoints: string[];
  citations: { url: string; title: string }[];
}

export interface SonarVideoProps {
  researchData: SonarResearchData;
  theme: Theme;
  durationInFrames: number;
}

function fadeUp(frame: number, delay = 0, duration = 20) {
  const f = Math.max(0, frame - delay);
  const opacity = interpolate(f, [0, duration], [0, 1], { extrapolateRight: 'clamp' });
  const y = interpolate(f, [0, duration], [30, 0], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
  return { opacity, transform: `translateY(${y}px)` };
}

// ---- Scene: Title (0 – 8s) --------------------------------------------------

const TitleScene: React.FC<{ data: SonarResearchData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();

  const barWidth = interpolate(frame, [5, 35], [0, 160], { extrapolateRight: 'clamp' });
  const titleAnim = fadeUp(frame, 8, 25);
  const tagAnim = fadeUp(frame, 28, 20);

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 28, padding: 80 }}>
      <div style={{
        width: barWidth,
        height: 5,
        backgroundColor: theme.accent,
        borderRadius: 3,
        marginBottom: 8,
      }} />
      <div style={{
        ...titleAnim,
        fontSize: 68,
        fontWeight: 800,
        color: theme.text,
        fontFamily: 'sans-serif',
        textAlign: 'center',
        maxWidth: 1200,
        letterSpacing: -2,
        lineHeight: 1.15,
      }}>
        {data.topic}
      </div>
      <div style={{
        ...tagAnim,
        fontSize: 22,
        color: theme.accent,
        fontFamily: 'monospace',
        letterSpacing: 4,
        textTransform: 'uppercase',
        marginTop: 8,
      }}>
        Research Insights
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene: Summary (8 – 16s) -----------------------------------------------

const SummaryScene: React.FC<{ data: SonarResearchData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();
  const labelAnim = fadeUp(frame, 0, 20);
  const textAnim = fadeUp(frame, 15, 25);

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 40, padding: 120 }}>
      <div style={{ ...labelAnim, fontSize: 22, color: theme.accent, fontFamily: 'monospace', letterSpacing: 4, textTransform: 'uppercase' }}>
        Summary
      </div>
      <div style={{
        ...textAnim,
        fontSize: 34,
        color: theme.text,
        fontFamily: 'sans-serif',
        textAlign: 'center',
        lineHeight: 1.6,
        maxWidth: 1100,
        fontWeight: 400,
      }}>
        {data.summary || 'Research findings from web analysis.'}
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene: Key Points (16 – 26s) -------------------------------------------

const KeyPointsScene: React.FC<{ data: SonarResearchData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();
  const titleAnim = fadeUp(frame, 0, 20);

  const points = (data.keyPoints || []).slice(0, 5);

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 40, padding: 100 }}>
      <div style={{ ...titleAnim, fontSize: 48, fontWeight: 700, color: theme.text, fontFamily: 'sans-serif' }}>
        Key Insights
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, width: '100%', maxWidth: 1100 }}>
        {points.map((point, i) => {
          const scale = spring({ frame: frame - (i * 10 + 15), fps: 30, config: { damping: 14, stiffness: 110 } });
          return (
            <div key={i} style={{
              transform: `scale(${scale})`,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 24,
              padding: '20px 32px',
              backgroundColor: `${theme.accent}12`,
              borderLeft: `4px solid ${theme.accent}`,
              borderRadius: '0 12px 12px 0',
            }}>
              <div style={{ fontSize: 28, color: theme.accent, fontWeight: 800, fontFamily: 'sans-serif', minWidth: 40 }}>
                {String(i + 1).padStart(2, '0')}
              </div>
              <div style={{ fontSize: 26, color: theme.text, fontFamily: 'sans-serif', lineHeight: 1.5 }}>
                {point}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene: Outro (26 – 30s) ------------------------------------------------

const OutroScene: React.FC<{ data: SonarResearchData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pulse = interpolate(Math.sin((frame / fps) * Math.PI * 2), [-1, 1], [0.97, 1.03]);
  const anim = fadeUp(frame, 0, 20);

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 28, padding: 80 }}>
      <div style={{
        ...anim,
        transform: `${anim.transform} scale(${pulse})`,
        fontSize: 76,
        fontWeight: 900,
        fontFamily: 'sans-serif',
        background: `linear-gradient(135deg, ${theme.accent}, ${theme.text})`,
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        textAlign: 'center',
        letterSpacing: -2,
      }}>
        {data.topic}
      </div>
      <div style={{ ...fadeUp(frame, 15, 20), fontSize: 24, color: theme.sub, fontFamily: 'sans-serif', letterSpacing: 3, textTransform: 'uppercase' }}>
        Powered by Zenvi AI Research
      </div>
    </AbsoluteFill>
  );
};

// ---- Main composition -------------------------------------------------------

export const SonarVideo: React.FC<SonarVideoProps> = ({ researchData, theme, durationInFrames }) => {
  const fps = 30;
  const title = Math.round(fps * 8);
  const summary = Math.round(fps * 8);
  const keyPoints = Math.round(fps * 10);
  const outro = durationInFrames - title - summary - keyPoints;

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg }}>
      <Sequence from={0} durationInFrames={title}>
        <TitleScene data={researchData} theme={theme} />
      </Sequence>
      <Sequence from={title} durationInFrames={summary}>
        <SummaryScene data={researchData} theme={theme} />
      </Sequence>
      <Sequence from={title + summary} durationInFrames={keyPoints}>
        <KeyPointsScene data={researchData} theme={theme} />
      </Sequence>
      <Sequence from={title + summary + keyPoints} durationInFrames={Math.max(1, outro)}>
        <OutroScene data={researchData} theme={theme} />
      </Sequence>
    </AbsoluteFill>
  );
};
