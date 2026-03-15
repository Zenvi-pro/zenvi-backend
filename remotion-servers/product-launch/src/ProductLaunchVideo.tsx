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

export interface Theme {
  bg: string;
  accent: string;
  text: string;
  sub: string;
}

export interface RepoData {
  owner: string;
  repo: string;
  name: string;
  description: string;
  stars: number;
  forks: number;
  language: string;
  topics: string[];
  homepage: string;
  readme: string;
}

export interface ProductLaunchVideoProps {
  repoData: RepoData;
  theme: Theme;
  durationInFrames: number;
}

// ---- Utilities -------------------------------------------------------------

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function useFadeUp(delay = 0, duration = 22) {
  const frame = useCurrentFrame();
  const f = Math.max(0, frame - delay);
  return {
    opacity: interpolate(f, [0, duration], [0, 1], { extrapolateRight: 'clamp' }),
    transform: `translateY(${interpolate(f, [0, duration], [36, 0], {
      extrapolateRight: 'clamp',
      easing: Easing.out(Easing.cubic),
    })}px)`,
  };
}

// ---- Scene 1: Hero (0 – 9s) ------------------------------------------------

const HeroScene: React.FC<{ data: RepoData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Animated background grid lines
  const gridOpacity = interpolate(frame, [0, 30], [0, 0.07], { extrapolateRight: 'clamp' });

  const taglineAnim = useFadeUp(0, 20);
  const titleAnim = useFadeUp(15, 25);
  const descAnim = useFadeUp(35, 22);
  const badgeScale = spring({ frame: frame - 50, fps, config: { damping: 12, stiffness: 100 } });

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, overflow: 'hidden' }}>
      {/* Subtle background grid */}
      <AbsoluteFill style={{
        backgroundImage: `linear-gradient(${theme.accent}20 1px, transparent 1px), linear-gradient(90deg, ${theme.accent}20 1px, transparent 1px)`,
        backgroundSize: '80px 80px',
        opacity: gridOpacity,
      }} />

      {/* Glow blob */}
      <div style={{
        position: 'absolute',
        width: 600,
        height: 600,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${theme.accent}18 0%, transparent 70%)`,
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
      }} />

      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 24, padding: 100 }}>
        <div style={{ ...taglineAnim, fontSize: 20, color: theme.accent, fontFamily: 'monospace', letterSpacing: 5, textTransform: 'uppercase' }}>
          Now Launching
        </div>

        <div style={{
          ...titleAnim,
          fontSize: 88,
          fontWeight: 900,
          fontFamily: 'sans-serif',
          color: theme.text,
          textAlign: 'center',
          letterSpacing: -3,
          lineHeight: 1.05,
          maxWidth: 1100,
        }}>
          {data.name || `${data.owner}/${data.repo}`}
        </div>

        {data.description && (
          <div style={{
            ...descAnim,
            fontSize: 30,
            color: theme.sub,
            fontFamily: 'sans-serif',
            textAlign: 'center',
            maxWidth: 860,
            lineHeight: 1.6,
          }}>
            {data.description}
          </div>
        )}

        {/* Language badge */}
        {data.language && (
          <div style={{
            transform: `scale(${badgeScale})`,
            marginTop: 8,
            padding: '10px 24px',
            backgroundColor: `${theme.accent}22`,
            border: `1.5px solid ${theme.accent}60`,
            borderRadius: 50,
            fontSize: 22,
            color: theme.accent,
            fontFamily: 'monospace',
            fontWeight: 600,
          }}>
            {data.language}
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// ---- Scene 2: Stats (9 – 19s) ----------------------------------------------

const StatItem: React.FC<{ icon: string; value: string; label: string; theme: Theme; delay: number }> = ({ icon, value, label, theme, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame: frame - delay, fps, config: { damping: 12, stiffness: 110 } });
  const opacity = interpolate(frame - delay, [0, 15], [0, 1], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' });

  return (
    <div style={{
      transform: `scale(${scale})`,
      opacity,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 16,
      padding: '48px 64px',
      background: `linear-gradient(145deg, ${theme.accent}14, ${theme.accent}06)`,
      border: `2px solid ${theme.accent}30`,
      borderRadius: 24,
      minWidth: 220,
    }}>
      <div style={{ fontSize: 52 }}>{icon}</div>
      <div style={{ fontSize: 56, fontWeight: 900, color: theme.accent, fontFamily: 'sans-serif', lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 20, color: theme.sub, fontFamily: 'sans-serif', textTransform: 'uppercase', letterSpacing: 3, fontWeight: 500 }}>{label}</div>
    </div>
  );
};

const StatsScene: React.FC<{ data: RepoData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();
  const titleAnim = useFadeUp(0, 20);

  const statItems = [
    { icon: '⭐', value: fmt(data.stars), label: 'Stars', delay: 15 },
    { icon: '🔀', value: fmt(data.forks), label: 'Forks', delay: 28 },
    { icon: '👁️', value: fmt(data.stars + data.forks), label: 'Engagement', delay: 41 },
  ];

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 64, padding: 80 }}>
      <div style={{ ...titleAnim, fontSize: 50, fontWeight: 700, color: theme.text, fontFamily: 'sans-serif', letterSpacing: -1 }}>
        By the Numbers
      </div>
      <div style={{ display: 'flex', gap: 48, flexWrap: 'wrap', justifyContent: 'center' }}>
        {statItems.map((s) => (
          <StatItem key={s.label} {...s} theme={theme} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene 3: Topics / Features (19 – 26s) ---------------------------------

const FeaturesScene: React.FC<{ data: RepoData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();
  const titleAnim = useFadeUp(0, 20);

  const items: string[] = data.topics.length > 0
    ? data.topics.slice(0, 6)
    : ['Fast', 'Reliable', 'Open Source'];

  // Extract feature-like lines from README
  const readmeFeatures: string[] = [];
  if (data.readme) {
    for (const line of data.readme.split('\n').slice(0, 60)) {
      const s = line.trim();
      if ((s.startsWith('- ') || s.startsWith('* ')) && s.length > 8 && s.length < 90) {
        const feat = s.slice(2).trim();
        if (feat && !feat.toLowerCase().startsWith('http')) {
          readmeFeatures.push(feat);
          if (readmeFeatures.length >= 4) break;
        }
      }
    }
  }

  const features = readmeFeatures.length > 0 ? readmeFeatures : items;

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 48, padding: 100 }}>
      <div style={{ ...titleAnim, fontSize: 50, fontWeight: 700, color: theme.text, fontFamily: 'sans-serif' }}>
        Why {data.name || data.repo}?
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20, width: '100%', maxWidth: 1000 }}>
        {features.map((feat, i) => {
          const s = spring({ frame: frame - (i * 10 + 15), fps: 30, config: { damping: 13, stiffness: 110 } });
          return (
            <div key={i} style={{
              transform: `scale(${s})`,
              display: 'flex',
              alignItems: 'center',
              gap: 20,
              padding: '18px 28px',
              backgroundColor: `${theme.accent}10`,
              borderLeft: `4px solid ${theme.accent}`,
              borderRadius: '0 14px 14px 0',
            }}>
              <div style={{ fontSize: 24, color: theme.accent, fontWeight: 800, fontFamily: 'sans-serif' }}>✦</div>
              <div style={{ fontSize: 28, color: theme.text, fontFamily: 'sans-serif', lineHeight: 1.4 }}>{feat}</div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene 4: CTA Outro (26 – 30s) ----------------------------------------

const CTAScene: React.FC<{ data: RepoData; theme: Theme }> = ({ data, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pulse = 1 + Math.sin((frame / fps) * Math.PI * 2) * 0.015;

  const ctaAnim = useFadeUp(0, 25);
  const urlAnim = useFadeUp(18, 20);
  const hpAnim = useFadeUp(28, 18);
  const taglineAnim = useFadeUp(35, 18);

  // Animated underline
  const underlineWidth = interpolate(frame, [20, 50], [0, 500], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 28, padding: 80 }}>
      <div style={{
        ...ctaAnim,
        transform: `${ctaAnim.transform} scale(${pulse})`,
        fontSize: 84,
        fontWeight: 900,
        fontFamily: 'sans-serif',
        background: `linear-gradient(135deg, ${theme.accent} 0%, ${theme.text} 100%)`,
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        letterSpacing: -3,
        textAlign: 'center',
      }}>
        Ship Something Great.
      </div>

      <div style={{
        width: underlineWidth,
        height: 3,
        backgroundColor: theme.accent,
        borderRadius: 2,
        opacity: 0.6,
      }} />

      <div style={{ ...urlAnim, fontSize: 32, color: theme.accent, fontFamily: 'monospace', fontWeight: 600 }}>
        github.com/{data.owner}/{data.repo}
      </div>

      {data.homepage && (
        <div style={{ ...hpAnim, fontSize: 24, color: theme.sub, fontFamily: 'sans-serif' }}>
          {data.homepage}
        </div>
      )}

      <div style={{ ...taglineAnim, fontSize: 20, color: theme.sub, fontFamily: 'sans-serif', letterSpacing: 3, textTransform: 'uppercase', marginTop: 12 }}>
        Built with Zenvi AI
      </div>
    </AbsoluteFill>
  );
};

// ---- Main composition -------------------------------------------------------

export const ProductLaunchVideo: React.FC<ProductLaunchVideoProps> = ({ repoData, theme, durationInFrames }) => {
  const fps = 30;
  const hero = Math.round(fps * 9);
  const stats = Math.round(fps * 10);
  const features = Math.round(fps * 7);
  const cta = durationInFrames - hero - stats - features;

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg }}>
      <Sequence from={0} durationInFrames={hero}>
        <HeroScene data={repoData} theme={theme} />
      </Sequence>
      <Sequence from={hero} durationInFrames={stats}>
        <StatsScene data={repoData} theme={theme} />
      </Sequence>
      <Sequence from={hero + stats} durationInFrames={features}>
        <FeaturesScene data={repoData} theme={theme} />
      </Sequence>
      <Sequence from={hero + stats + features} durationInFrames={Math.max(1, cta)}>
        <CTAScene data={repoData} theme={theme} />
      </Sequence>
    </AbsoluteFill>
  );
};
