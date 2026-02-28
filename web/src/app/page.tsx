import Link from 'next/link';
import styles from './page.module.css';

export default function Home() {
  return (
    <main className={styles.main} style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>ExplainFlow</h1>
      <p>Convert ideas into visual narrative pipelines.</p>
      
      <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
        <Link href="/quick" style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px', textDecoration: 'none', color: 'inherit' }}>
          <h2>Quick Generate &rarr;</h2>
          <p>Prompt-based, one-click explainer.</p>
        </Link>
        
        <Link href="/advanced" style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '8px', textDecoration: 'none', color: 'inherit' }}>
          <h2>Advanced Studio &rarr;</h2>
          <p>Long-form input and granular visual control.</p>
        </Link>
      </div>
    </main>
  );
}
