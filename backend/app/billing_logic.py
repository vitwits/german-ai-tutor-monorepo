"""
Energy-based billing system logic
Handles monthly credit allocation, energy point calculations, and spending tracking
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from calendar import monthrange
import math


class BillingInitializer:
    """Handles initialization of billing for new users"""
    
    @staticmethod
    def initialize_user_billing(
        user_id: str,
        monthly_credit_usd: float,
        max_cap_days: int,
        current_date: datetime = None
    ) -> dict:
        """
        Initialize billing for new user at registration
        
        Args:
            user_id: User ID
            monthly_credit_usd: Monthly budget from BillingPlan
            max_cap_days: Max cap days from BillingPlan
            current_date: Registration date (default: now)
        
        Returns:
            Dictionary with initial billing data
        """
        if current_date is None:
            current_date = datetime.utcnow()
        
        billing_start_day = current_date.day
        
        # Calculate billing_end_day (day of next month when period ends)
        # If period starts on day X, it ends on day X of next month (inclusive)
        billing_end_day = billing_start_day
        
        # Calculate initial energy
        daily_energy, price_per_point = BillingCalculator.calculate_daily_energy_budget(
            monthly_credit_usd,
            billing_start_day,
            current_date
        )
        
        # Initial energy is 1 day worth (grace period for first day)
        initial_energy = daily_energy
        
        return {
            "user_id": user_id,
            "subscription_status": "active",
            "billing_start_day": billing_start_day,
            "billing_end_day": billing_end_day,
            "energy_left": initial_energy,
            "daily_spending": 0.0,
            "price_per_point_usd": price_per_point,
            "last_energy_reset": current_date,
            "last_billing_reset": current_date
        }


class BillingManager:
    """Handles daily and periodic billing updates"""
    
    @staticmethod
    async def process_daily_reset(
        user_billing,
        monthly_credit_usd: float,
        max_cap_days: int,
        current_date: datetime = None
    ) -> dict:
        """
        Process daily energy reset at 00:00
        
        Args:
            user_billing: UserBilling record
            monthly_credit_usd: Monthly budget from BillingPlan
            max_cap_days: Max cap days from BillingPlan
            current_date: Current datetime (default: now)
        
        Returns:
            Dictionary with updated fields
        """
        if current_date is None:
            current_date = datetime.utcnow()
        
        # Check if we need to reset energy (new day)
        should_reset = BillingCalculator.should_reset_energy(
            user_billing.last_energy_reset,
            current_date
        )
        
        if not should_reset:
            return {}  # No reset needed
        
        # Check if we're in a new billing period
        new_billing_period = BillingCalculator.should_start_new_billing_period(
            user_billing.billing_start_day,
            user_billing.last_billing_reset,
            current_date
        )
        
        # Calculate current price per point
        daily_energy, price_per_point = BillingCalculator.calculate_daily_energy_budget(
            monthly_credit_usd,
            user_billing.billing_start_day,
            current_date
        )
        
        # Calculate max cap
        max_energy_cap = BillingCalculator.calculate_max_energy_cap(
            monthly_credit_usd,
            max_cap_days,
            user_billing.billing_start_day,
            current_date
        )
        
        updates = {
            "daily_spending": 0.0,  # Reset daily spending
            "price_per_point_usd": price_per_point,
            "last_energy_reset": current_date
        }
        
        if new_billing_period:
            # New billing period started - full reset of energy
            updates["energy_left"] = daily_energy
            updates["last_billing_reset"] = current_date
            updates["subscription_status"] = "active"
        else:
            # Same billing period - add daily energy, but cap it
            new_energy = user_billing.energy_left + daily_energy
            updates["energy_left"] = BillingCalculator.get_energy_after_cap(
                new_energy,
                max_energy_cap
            )
        
        return updates
    
    @staticmethod
    def deduct_spending(
        user_billing,
        spending_usd: float,
        monthly_credit_usd: float
    ) -> dict:
        """
        Deduct energy based on spending
        
        Args:
            user_billing: UserBilling record
            spending_usd: Amount spent in USD
            monthly_credit_usd: Monthly budget (for price calculation)
        
        Returns:
            Dictionary with updated fields
        """
        # Deduct from energy
        remaining_energy, energy_spent = BillingCalculator.deduct_energy_for_spending(
            user_billing.energy_left,
            spending_usd,
            user_billing.price_per_point_usd
        )
        
        # Update daily spending
        new_daily_spending = user_billing.daily_spending + spending_usd
        
        # Check if we're out of energy
        subscription_status = "inactive" if remaining_energy <= 0 else "active"
        
        return {
            "energy_left": remaining_energy,
            "daily_spending": new_daily_spending,
            "subscription_status": subscription_status
        }
    
    @staticmethod
    def can_spend_energy(
        user_billing,
        spending_usd: float
    ) -> bool:
        """
        Check if user has enough energy for spending
        
        Args:
            user_billing: UserBilling record
            spending_usd: Amount to spend in USD
        
        Returns:
            True if user can afford it
        """
        if user_billing.price_per_point_usd <= 0:
            return True  # Free tier
        
        energy_needed = spending_usd / user_billing.price_per_point_usd
        return user_billing.energy_left >= energy_needed


class BillingCalculator:
    """Handles all billing calculations and energy management"""
    
    @staticmethod
    def get_days_in_current_month(date: datetime = None) -> int:
        """Get number of days in the current month"""
        if date is None:
            date = datetime.utcnow()
        _, days = monthrange(date.year, date.month)
        return days
    
    @staticmethod
    def get_days_until_next_billing_date(start_day: int, current_date: datetime = None) -> int:
        """
        Calculate days from current_date until next billing date (start_day of next month)
        
        Args:
            start_day: Day of month when billing period started (1-31)
            current_date: Reference date (default: today)
        
        Returns:
            Number of days remaining in current billing period
        """
        if current_date is None:
            current_date = datetime.utcnow()
        
        current_day = current_date.day
        year = current_date.year
        month = current_date.month
        
        # If we haven't reached start_day this month yet
        if current_day < start_day:
            return start_day - current_day
        
        # Calculate days until start_day next month
        days_in_current_month = monthrange(year, month)[1]
        days_until_month_end = days_in_current_month - current_day
        days_until_next_start = days_until_month_end + start_day
        
        return days_until_next_start
    
    @staticmethod
    def get_billing_period_days(start_day: int, current_date: datetime = None) -> int:
        """
        Get total days in current billing period (from start_day to start_day next month)
        
        Args:
            start_day: Day of month when billing period started (1-31)
            current_date: Reference date (default: today)
        
        Returns:
            Total days in billing period
        """
        if current_date is None:
            current_date = datetime.utcnow()
        
        year = current_date.year
        month = current_date.month
        
        # Days from start_day to end of current month
        days_in_current_month = monthrange(year, month)[1]
        if current_date.day >= start_day:
            days_remaining_in_current = days_in_current_month - start_day + 1
        else:
            # Period hasn't started this month yet, check previous month
            prev_month = month - 1 if month > 1 else 12
            prev_year = year if month > 1 else year - 1
            days_in_prev_month = monthrange(prev_year, prev_month)[1]
            days_remaining_in_current = days_in_prev_month - start_day + 1
        
        # Days from 1st to start_day-1 of next month
        days_in_next_month_period = start_day - 1
        
        return days_remaining_in_current + days_in_next_month_period
    
    @staticmethod
    def calculate_energy_price_per_point(
        monthly_credit_usd: float,
        billing_start_day: int,
        current_date: datetime = None
    ) -> float:
        """
        Calculate cost in USD for 1 energy point
        
        Formula: monthly_credit_usd / days_in_period / daily_energy_points
        
        Args:
            monthly_credit_usd: Monthly budget in USD
            billing_start_day: Day of month billing period starts
            current_date: Reference date (default: today)
        
        Returns:
            Cost in USD for 1 energy point
        """
        if current_date is None:
            current_date = datetime.utcnow()
        
        days_in_period = BillingCalculator.get_billing_period_days(billing_start_day, current_date)
        
        if days_in_period == 0:
            return 0
        
        # Price per day in USD
        price_per_day = monthly_credit_usd / days_in_period
        
        # Price per energy point (100 points per day)
        price_per_point = price_per_day / 100.0
        
        return price_per_point
    
    @staticmethod
    def calculate_daily_energy_budget(
        monthly_credit_usd: float,
        billing_start_day: int,
        current_date: datetime = None
    ) -> Tuple[float, float]:
        """
        Calculate daily energy budget and price per point
        
        Args:
            monthly_credit_usd: Monthly budget in USD
            billing_start_day: Day of month billing period starts
            current_date: Reference date (default: today)
        
        Returns:
            Tuple of (daily_energy_points_budget, price_per_point_usd)
        """
        price_per_point = BillingCalculator.calculate_energy_price_per_point(
            monthly_credit_usd, 
            billing_start_day,
            current_date
        )
        
        # 100 energy points per day (fixed)
        daily_energy = 100.0
        
        return daily_energy, price_per_point
    
    @staticmethod
    def should_reset_energy(
        last_energy_reset: datetime,
        current_date: datetime = None
    ) -> bool:
        """
        Check if energy should be reset (new day at 00:00)
        
        Args:
            last_energy_reset: Datetime of last energy reset
            current_date: Reference date (default: now)
        
        Returns:
            True if current date is different from last reset date
        """
        if current_date is None:
            current_date = datetime.utcnow()
        
        return last_energy_reset.date() != current_date.date()
    
    @staticmethod
    def should_start_new_billing_period(
        billing_start_day: int,
        last_billing_reset: datetime,
        current_date: datetime = None
    ) -> bool:
        """
        Check if new billing period should start
        
        Args:
            billing_start_day: Day of month when billing period starts
            last_billing_reset: Datetime of last billing period reset
            current_date: Reference date (default: now)
        
        Returns:
            True if new billing period has started
        """
        if current_date is None:
            current_date = datetime.utcnow()
        
        last_date = last_billing_reset.date()
        curr_date = current_date.date()
        
        # Check if we've crossed into a new period
        # (current day >= start_day and last day < start_day OR different months)
        
        if last_date.month != curr_date.month:
            # Different month - check if current day is >= start_day
            return curr_date.day >= billing_start_day
        
        # Same month - only new period if we crossed the boundary
        return False
    
    @staticmethod
    def calculate_max_energy_cap(
        monthly_credit_usd: float,
        max_cap_days: int,
        billing_start_day: int,
        current_date: datetime = None
    ) -> float:
        """
        Calculate maximum energy that can be accumulated (based on max_cap_days)
        
        Args:
            monthly_credit_usd: Monthly budget in USD
            max_cap_days: Maximum days of credit that can accumulate
            billing_start_day: Day of month billing period starts
            current_date: Reference date (default: today)
        
        Returns:
            Maximum energy points (100 * max_cap_days)
        """
        # Max energy is simply 100 points * max_cap_days
        return 100.0 * max_cap_days
    
    @staticmethod
    def get_energy_after_cap(
        current_energy: float,
        max_energy_cap: float
    ) -> float:
        """
        Apply energy cap - energy cannot exceed the cap
        
        Args:
            current_energy: Current energy points
            max_energy_cap: Maximum allowed energy
        
        Returns:
            Energy capped to maximum
        """
        return min(current_energy, max_energy_cap)
    
    @staticmethod
    def deduct_energy_for_spending(
        current_energy: float,
        spending_usd: float,
        price_per_point: float
    ) -> Tuple[float, float]:
        """
        Deduct energy based on USD spending
        
        Args:
            current_energy: Current energy points
            spending_usd: Amount spent in USD
            price_per_point: Cost in USD for 1 energy point
        
        Returns:
            Tuple of (remaining_energy, energy_spent)
        """
        if price_per_point <= 0:
            return current_energy, 0.0
        
        energy_spent = spending_usd / price_per_point
        remaining_energy = max(0.0, current_energy - energy_spent)
        
        return remaining_energy, energy_spent
    
    @staticmethod
    def get_energy_status(
        energy_left: float,
        daily_spending: float,
        price_per_point: float
    ) -> dict:
        """
        Get current energy status summary
        
        Args:
            energy_left: Current energy points
            daily_spending: USD spent today
            price_per_point: Cost in USD for 1 energy point
        
        Returns:
            Dictionary with status info
        """
        daily_spent_energy = daily_spending / price_per_point if price_per_point > 0 else 0.0
        daily_remaining_energy = 100.0 - daily_spent_energy
        
        return {
            "energy_left": round(energy_left, 2),
            "daily_budget": 100.0,
            "daily_spent_energy": round(daily_spent_energy, 2),
            "daily_remaining_energy": round(max(0.0, daily_remaining_energy), 2),
            "price_per_point_usd": round(price_per_point, 8)
        }


# Global instances for use throughout the app
billing_calc = BillingCalculator()
billing_init = BillingInitializer()
billing_manager = BillingManager()
