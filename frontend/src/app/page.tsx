import Link from "next/link";

const categories = [
  ["Scholarships", "Reviewed awards matched to your academic profile."],
  ["Grants", "Need-based and purpose-specific funding opportunities."],
  ["Student support", "Food, housing, and emergency resources in one place."],
];

export default function LandingPage() {
  return (
    <main>
      <header className="site-header">
        <Link className="brand" href="/" aria-label="PathAid home">
          <span className="brand-mark" aria-hidden="true">◒</span><span>PathAid</span>
        </Link>
        <nav className="header-actions" aria-label="Account">
          <Link className="button button-quiet" href="/login">Log in</Link>
          <Link className="button button-primary" href="/signup">Create account</Link>
        </nav>
      </header>

      <section className="hero page-width">
        <div className="hero-copy">
          <p className="eyebrow"><span aria-hidden="true">●</span> Reviewed opportunities, clear answers</p>
          <h1>Find financial support you can understand.</h1>
          <p className="hero-lede">PathAid matches your profile with scholarships and student resources, then shows the reviewed requirements and official source behind every result.</p>
          <div className="hero-actions">
            <Link className="button button-primary button-large" href="/signup">Build your profile</Link>
            <Link className="text-link" href="/login">I already have an account <span aria-hidden="true">→</span></Link>
          </div>
          <p className="privacy-note">Your eligibility is evaluated by transparent rules. AI never decides whether you qualify.</p>
        </div>

        <aside className="match-preview" aria-label="Example scholarship match">
          <div className="preview-topline"><span className="status-dot" /> Example reviewed match</div>
          <div className="preview-card">
            <div className="preview-meta">Ada Lovelace Foundation <span className="badge">Verified source</span></div>
            <h2>STEM Leadership Grant</h2>
            <p>Support for undergraduate students building technical and community leadership.</p>
            <div className="preview-facts">
              <span><small>Award</small><strong>$10,000</strong></span>
              <span><small>Availability</small><strong>Open</strong></span>
            </div>
          </div>
          <div className="reason-card">
            <strong>Why it may fit</strong>
            <p>Profile details are compared with reviewed criteria. Missing information stays clearly labeled.</p>
          </div>
        </aside>
      </section>

      <section className="category-section page-width" aria-labelledby="support-heading">
        <div><p className="eyebrow">One profile, several kinds of support</p><h2 id="support-heading">Start with what you need</h2></div>
        <div className="category-grid">
          {categories.map(([title, description], index) => (
            <article className="category-card" key={title}>
              <span className="category-number" aria-hidden="true">0{index + 1}</span>
              <h3>{title}</h3><p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="trust-section">
        <div className="page-width trust-grid">
          <div><p className="eyebrow">Built for informed decisions</p><h2>Know why a result appears.</h2></div>
          <ul>
            <li><strong>Source backed</strong><span>See the official evidence and verification date.</span></li>
            <li><strong>Honest about unknowns</strong><span>Missing answers and provider decisions stay visible.</span></li>
            <li><strong>Private by design</strong><span>Choose whether relevant profile details may be used for an optional AI explanation.</span></li>
          </ul>
        </div>
      </section>
    </main>
  );
}
