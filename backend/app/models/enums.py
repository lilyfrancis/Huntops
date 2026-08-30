import enum


class UserRole(str, enum.Enum):
    job_seeker = "job_seeker"
    employer = "employer"
    admin = "admin"


class SubscriptionTier(str, enum.Enum):
    free = "free"
    pro = "pro"
    elite = "elite"


class JobStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    rejected = "rejected"
    closed = "closed"


class JobType(str, enum.Enum):
    full_time = "full_time"
    part_time = "part_time"
    contract = "contract"
    internship = "internship"


class ExperienceLevel(str, enum.Enum):
    entry = "entry"
    mid = "mid"
    senior = "senior"
    lead = "lead"
    executive = "executive"


class JobLane(str, enum.Enum):
    """Broad functional category, inferred from title/description at ingest time.

    Job Engine's original taxonomy (GTM/RevOps/Automation/WordPress/BDM/
    Leadership/Operations/Marketing) was tuned for one RevOps/GTM persona and
    dropped anything that didn't match. A general marketplace can't drop most
    of its supply, so this is broadened with engineering/product/design/etc.
    and unmatched jobs fall through to `other` instead of being discarded.
    """

    engineering = "engineering"
    product = "product"
    design = "design"
    gtm = "gtm"
    revops = "revops"
    marketing = "marketing"
    sales = "sales"
    automation = "automation"
    operations = "operations"
    leadership = "leadership"
    customer_success = "customer_success"
    finance = "finance"
    hr = "hr"
    other = "other"


class ApplicationStatus(str, enum.Enum):
    pending = "pending"
    reviewed = "reviewed"
    interviewing = "interviewing"
    offered = "offered"
    rejected = "rejected"
    withdrawn = "withdrawn"
