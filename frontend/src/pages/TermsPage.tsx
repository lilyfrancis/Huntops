import { LegalLayout } from "@/components/layout/legal-layout";

export function TermsPage() {
  return (
    <LegalLayout title="Terms of Service" updated="6 September 2026">
      <p>
        These terms govern your use of HuntOps at{" "}
        <a href="https://huntops.site">huntops.site</a>. By creating an account you agree to them.
      </p>

      <h2>What HuntOps does</h2>
      <p>
        HuntOps aggregates job listings from public job boards and from email job alerts received
        by mailboxes we operate, scores them against your CV, and can draft and send outreach on
        your behalf. It also offers mock interviews and offer-negotiation guidance.
      </p>

      <h2>What HuntOps is not</h2>
      <ul>
        <li>
          <strong>It is not an employer or a recruiter.</strong> We do not offer jobs, guarantee
          interviews, or represent you to anyone.
        </li>
        <li>
          <strong>It is not legal, financial or career advice.</strong> The negotiation coach and
          interview feedback are AI-generated suggestions based on the information available. Treat
          them as a starting point, not a professional opinion.
        </li>
        <li>
          <strong>We do not control the listings.</strong> Most jobs come from third-party sources.
          We flag listings that look stale or repeatedly reposted, but we cannot verify that any
          role is real, open, or accurately described.
        </li>
      </ul>

      <h2>Your account</h2>
      <p>
        You must be at least 16. Give accurate information, keep your password to yourself, and
        tell us if you think someone else has got into your account. You are responsible for what
        happens under it.
      </p>

      <h2>Autopilot</h2>
      <p>
        If you switch autopilot on, HuntOps will submit applications and send outreach messages in
        your name, without asking you first, whenever a job clears the score threshold you set.
        That is the entire point of the feature and you should turn it on deliberately.
      </p>
      <ul>
        <li>It is off unless you turn it on.</li>
        <li>It never acts below the threshold you set, or beyond your daily cap.</li>
        <li>Every action and every skip is listed on your Autopilot page.</li>
        <li>
          <strong>You are responsible for what it sends.</strong> Messages are drafted from your CV
          and the job listing; review the log, and switch it off if you are not comfortable.
        </li>
      </ul>

      <h2>Acceptable use</h2>
      <p>Do not use HuntOps to:</p>
      <ul>
        <li>Misrepresent your identity, experience or qualifications;</li>
        <li>Send bulk unsolicited mail beyond genuine job outreach;</li>
        <li>Scrape, resell or redistribute the job data;</li>
        <li>Attempt to break, overload or gain unauthorised access to the service;</li>
        <li>Post job listings that are fraudulent, discriminatory, or not real openings.</li>
      </ul>
      <p>We may suspend an account that does any of this.</p>

      <h2>Plans, credits and payment</h2>
      <p>
        Free, Pro and Elite plans each come with a monthly allowance of AI credits. Actions that
        cost us money — scoring, drafting, interviews, negotiation reviews — spend credits.
        Payments are handled by Paystack; your card details never reach us.
      </p>
      <ul>
        <li>Subscriptions renew monthly until you cancel.</li>
        <li>
          Cancelling stops the next renewal. You keep your plan until the end of the period you
          have already paid for.
        </li>
        <li>Unused credits do not carry over between months and have no cash value.</li>
        <li>
          We do not offer refunds for partial months, except where the law where you live requires
          it.
        </li>
      </ul>
      <p>
        We may change prices with at least 30 days' notice by email. The new price applies from
        your next renewal.
      </p>

      <h2>Your content</h2>
      <p>
        Your CV and everything you write stays yours. You give us permission to store and process
        it only to run the features you are using. We do not use it to train AI models, and we do
        not sell it.
      </p>

      <h2>Availability</h2>
      <p>
        We aim to keep HuntOps running but do not promise it will be uninterrupted or error-free.
        Job sources go down, third-party APIs fail, and we take the service offline for
        maintenance. We may change or discontinue features; if we discontinue something you are
        paying for, you can cancel and we will refund the unused part of that period.
      </p>

      <h2>Liability</h2>
      <p>
        To the fullest extent the law allows, HuntOps is provided as-is, and we are not liable for
        indirect or consequential loss — including a job you did not get, an offer you did not
        receive, or a decision you made on the basis of something the service told you. Where
        liability cannot be excluded, it is limited to what you paid us in the twelve months before
        the claim. Nothing here limits liability for fraud, death or personal injury caused by
        negligence, or anything else that cannot lawfully be limited.
      </p>

      <h2>Ending it</h2>
      <p>
        You can delete your account whenever you like. We may suspend or close an account that
        breaks these terms, and will tell you why unless we are legally prevented from doing so.
      </p>

      <h2>Changes</h2>
      <p>
        We will email you before any material change takes effect. Continuing to use HuntOps after
        that means you accept the new terms.
      </p>

      <h2>Contact</h2>
      <p>
        <a href="mailto:support@huntops.site">support@huntops.site</a>
      </p>
    </LegalLayout>
  );
}
