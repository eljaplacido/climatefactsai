import { CheckCircle, XCircle, AlertCircle, HelpCircle } from 'lucide-react';
import clsx from 'clsx';
import type { FactCheck } from '../types';

interface FactCheckBadgeProps {
  factCheck: FactCheck;
  size?: 'sm' | 'md' | 'lg';
}

function FactCheckBadge({ factCheck, size = 'md' }: FactCheckBadgeProps) {
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'VERIFIED':
        return {
          icon: CheckCircle,
          label: 'Todennettu',
          bg: 'bg-green-50',
          text: 'text-green-700',
          border: 'border-green-200'
        };
      case 'UNVERIFIED':
        return {
          icon: XCircle,
          label: 'Ei todennettu',
          bg: 'bg-red-50',
          text: 'text-red-700',
          border: 'border-red-200'
        };
      case 'DISPUTED':
        return {
          icon: AlertCircle,
          label: 'Kiistelty',
          bg: 'bg-orange-50',
          text: 'text-orange-700',
          border: 'border-orange-200'
        };
      case 'PARTIALLY_VERIFIED':
        return {
          icon: AlertCircle,
          label: 'Osittain todennettu',
          bg: 'bg-yellow-50',
          text: 'text-yellow-700',
          border: 'border-yellow-200'
        };
      default:
        return {
          icon: HelpCircle,
          label: 'Tuntematon',
          bg: 'bg-gray-50',
          text: 'text-gray-700',
          border: 'border-gray-200'
        };
    }
  };

  const sizeClasses = {
    sm: 'text-xs px-2 py-1',
    md: 'text-sm px-3 py-1.5',
    lg: 'text-base px-4 py-2'
  };

  const iconSizes = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-5 w-5'
  };

  const config = getStatusConfig(factCheck.verification_status);
  const Icon = config.icon;

  return (
    <div className={clsx(
      'inline-flex items-center space-x-2 rounded-full font-medium border',
      config.bg,
      config.text,
      config.border,
      sizeClasses[size]
    )}>
      <Icon className={iconSizes[size]} />
      <span>{config.label}</span>
      <span className="opacity-75">({Math.round(factCheck.confidence_score)}%)</span>
    </div>
  );
}

export default FactCheckBadge;

