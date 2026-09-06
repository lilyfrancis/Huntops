import { LegalLayout } from "@/components/layout/legal-layout";

/*
  Describes what the system actually does, not a template. Every claim here
  maps to real code — the Gmail section in particular, because Google checks
  it against the scopes the OAuth client requests.
*/
export function PrivacyPage() {
  return (
    <LegalLayout title="Privacy Policy" updated="6 September 2026">
      <p>
        HuntOps ("we", "us") runs a job-search service at{" "}
        <a href="https://huntops.site">huntops.site</a>. This policy explains what we collect, why,
        who we share it with, and how to get it deleted. It is written to be read, not to be
        survived.
      </p>

      <h2>Who we are</h2>
      <p>
        HuntOps is the data controller for the information described below. You can reach us at{" "}
        <a href="mailto:privacy@huntops.site">privacy@huntops.site</a> for any question or request
        in this policy.
      </p>

      <h2>What we collect</h2>
      <table>
        <thead>
          <tr>
            <th>What</th>
            <th>Why</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Name, email address, password (hashed)</td>
            <td>To create and secure your account</td>
          </tr>
          <tr>
            <td>Target markets, job families, employment types, remote preference</td>
            <td>To decide which jobs appear in your feed</td>
          </tr>
          <tr>
            <td>Your CV file and the text, skills and experience parsed from it</td>
            <td>To score how well each job fits you, and to draft outreach</td>
          </tr>
          <tr>
            <td>Applications, outreach drafts, interview answers, offer details</td>
            <td>To provide those features and show you your own history</td>
          </tr>
          <tr>
            <td>Payment identifiers from Paystack (customer and subscription codes)</td>
            <td>To know which plan you are on. We never see or store your card details.</td>
          </tr>
          <tr>
            <td>Server logs: request paths, status codes, timings</td>
            <td>To keep the service running and diagnose faults</td>
          </tr>
        </tbody>
      </table>

      <h2>Google account data</h2>
      <p>
        There are two entirely separate Google connections in HuntOps, and it matters which is
        which.
      </p>

      <h3>Mailboxes we operate</h3>
      <p>
        The jobs in your feed come from a small set of email accounts <strong>we</strong> own and
        subscribe to job alerts. Those are our accounts, not yours. You never connect an inbox to
        get a job feed, and we never read your personal mail to find you jobs.
      </p>

      <h3>Sending outreach from your address (optional)</h3>
      <p>
        If — and only if — you choose to connect your own Gmail on the integrations page, HuntOps
        requests the <strong>send</strong> permission and nothing else. We cannot read, list,
        search, label or delete anything in your mailbox, because we never ask for the permission
        that would allow it. We use it solely to send outreach messages you have asked us to send,
        from your address, so replies reach you directly. You can disconnect at any time on that
        page, which revokes the grant at Google and deletes the stored tokens.
      </p>
      <p>
        If you do not connect Gmail, outreach is sent from our own address with your email set as
        the reply-to, so the feature works without any access to your account.
      </p>

      <h3>Limited Use</h3>
      <p>
        HuntOps' use and transfer of information received from Google APIs to any other app will
        adhere to the{" "}
        <a
          href="https://developers.google.com/terms/api-services-user-data-policy"
          target="_blank"
          rel="noreferrer noopener"
        >
          Google API Services User Data Policy
        </a>
        , including the Limited Use requirements. Specifically: we do not use Google user data to
        serve advertising, we do not sell it, we do not transfer it except as needed to provide the
        features you asked for, and no human reads it except where you have explicitly asked us to,
        for security purposes, or where the law requires it.
      </p>

      <h2>Automated processing</h2>
      <p>
        HuntOps scores jobs against your CV and can, if you switch it on, apply to jobs or send
        outreach on your behalf without asking each time. Autopilot is off by default, only acts
        above a score threshold you set, and is capped at a number of actions per day you choose.
        Everything it does — including the jobs it considered and passed on — is listed on your
        Autopilot page, and you can switch it off at any moment.
      </p>

      <h2>Who we share it with</h2>
      <p>We use a small number of processors, each for one job:</p>
      <ul>
        <li>
          <strong>Anthropic</strong> — CV parsing, job fit scoring, interview grading and drafting
          outreach. Relevant excerpts of your CV and the job description are sent for processing.
        </li>
        <li>
          <strong>Apollo.io</strong> — finding a hiring contact at a company you are reaching out
          to. We send the company name; we do not send your CV or personal details.
        </li>
        <li>
          <strong>Paystack</strong> — payment processing. Your card details go to Paystack directly
          and never touch our servers.
        </li>
        <li>
          <strong>Google</strong> — only for the Gmail connections described above.
        </li>
        <li>
          <strong>Our email provider</strong> — to deliver your daily digest and, where you have
          not connected Gmail, your outreach.
        </li>
        <li>
          <strong>Amazon Web Services</strong> — hosting.
        </li>
      </ul>
      <p>
        We do not sell your data, and we do not share it with advertisers. When you apply to a job
        posted directly on HuntOps, the employer who posted it sees your name, email and
        application — which is the point of applying.
      </p>

      <h2>Where your data is held</h2>
      <p>
        Our servers are in the European Union (London). If you are outside that region, using
        HuntOps means your data is transferred there.
      </p>

      <h2>How long we keep it</h2>
      <ul>
        <li>Account data: until you delete your account.</li>
        <li>
          CVs, applications, outreach, interviews and offers: until you delete them or your
          account.
        </li>
        <li>Gmail tokens: until you disconnect, or your account is deleted.</li>
        <li>Server logs: 30 days.</li>
        <li>
          Payment records: retained as long as tax and accounting law requires, typically six to
          seven years.
        </li>
      </ul>

      <h2>Your rights</h2>
      <p>
        You can ask us to give you a copy of your data, correct it, delete it, or stop a particular
        use of it. Email <a href="mailto:privacy@huntops.site">privacy@huntops.site</a> and we will
        respond within 30 days. Deleting your account removes your profile, CV, preferences,
        applications, outreach, interviews and offers, and revokes any Gmail connection.
      </p>
      <p>
        Depending on where you live you may also have the right to complain to a data protection
        authority — the ICO in the UK, your provincial or federal Privacy Commissioner in Canada,
        or the NDPC in Nigeria.
      </p>

      <h2>Security</h2>
      <p>
        Passwords are hashed with bcrypt and never stored in a readable form. Gmail tokens are
        encrypted at rest. All traffic to the site is over HTTPS. The database is not reachable
        from the public internet. No system is perfect, and we will tell you promptly if we
        discover a breach affecting your data.
      </p>

      <h2>Children</h2>
      <p>HuntOps is not for anyone under 16, and we do not knowingly collect their data.</p>

      <h2>Changes</h2>
      <p>
        If we change this policy materially we will email you before it takes effect. The date at
        the top always reflects the current version.
      </p>
    </LegalLayout>
  );
}
